"""Skema Pydantic untuk autentikasi & registrasi (FR-01)."""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models.user import UserRole

_PHONE_RE = re.compile(r"^\+?[0-9\s\-]{10,20}$")


class SppgOfficerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    nip: str
    sppg_unit: str
    region: str
    position: str | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    phone: str | None = None
    role: UserRole
    is_active: bool = True
    created_at: datetime
    sppg_officer: SppgOfficerOut | None = None


class AuthSession(BaseModel):
    user: UserOut
    token: str


class RegisterRequest(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str | None = None
    role: UserRole = UserRole.USER

    # Field khusus petugas SPPG MBG.
    nip: str | None = Field(default=None, max_length=50)
    sppg_unit: str | None = Field(default=None, max_length=150)
    region: str | None = Field(default=None, max_length=100)
    position: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_registration(self) -> "RegisterRequest":
        if self.role not in (UserRole.USER, UserRole.PETUGAS_SPPG):
            raise ValueError("Peran hanya boleh 'user' atau 'petugas_sppg'.")

        if not any(char.isalpha() for char in self.password) or not any(
            char.isdigit() for char in self.password
        ):
            raise ValueError("Password harus memuat huruf dan angka.")

        if self.confirm_password is not None and self.confirm_password != self.password:
            raise ValueError("Konfirmasi password tidak sama.")

        if self.role == UserRole.PETUGAS_SPPG:
            missing = [
                label
                for label, value in (
                    ("NIP", self.nip),
                    ("unit SPPG", self.sppg_unit),
                    ("wilayah", self.region),
                )
                if not (value or "").strip()
            ]
            if missing:
                raise ValueError("Data petugas SPPG wajib diisi: " + ", ".join(missing) + ".")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


# ---------------------------------------------------------------------------
# Manajemen pengguna oleh admin
# ---------------------------------------------------------------------------


class UserListItem(UserOut):
    """Item daftar pengguna untuk panel admin (menyertakan jumlah sekolah)."""

    schools_count: int = 0


class UserCreateRequest(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.USER
    is_active: bool = True

    nip: str | None = Field(default=None, max_length=50)
    sppg_unit: str | None = Field(default=None, max_length=150)
    region: str | None = Field(default=None, max_length=100)
    position: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def _validate(self) -> "UserCreateRequest":
        if self.role not in (UserRole.USER, UserRole.PETUGAS_SPPG, UserRole.ADMIN):
            raise ValueError("Peran tidak valid untuk dibuat admin.")
        if not any(c.isalpha() for c in self.password) or not any(
            c.isdigit() for c in self.password
        ):
            raise ValueError("Password harus memuat huruf dan angka.")
        if self.role == UserRole.PETUGAS_SPPG:
            missing = [
                label
                for label, value in (
                    ("NIP", self.nip),
                    ("unit SPPG", self.sppg_unit),
                    ("wilayah", self.region),
                )
                if not (value or "").strip()
            ]
            if missing:
                raise ValueError("Data petugas SPPG wajib diisi: " + ", ".join(missing) + ".")
        return self


class UserUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=100)
    role: UserRole | None = None
    is_active: bool | None = None
    nip: str | None = Field(default=None, max_length=50)
    sppg_unit: str | None = Field(default=None, max_length=150)
    region: str | None = Field(default=None, max_length=100)
    position: str | None = Field(default=None, max_length=100)


# ---------------------------------------------------------------------------
# Halaman Profil — akun (FR-02)
# ---------------------------------------------------------------------------


def _validate_phone(value: str | None) -> str | None:
    """Nomor HP opsional, 10-15 digit (boleh diawali + dan dipisah spasi/strip)."""
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if not _PHONE_RE.match(cleaned):
        raise ValueError("Format nomor HP tidak valid (10-15 digit angka).")
    digits = len(re.sub(r"\D", "", cleaned))
    if not 10 <= digits <= 15:
        raise ValueError("Nomor HP harus terdiri dari 10-15 digit.")
    return cleaned


class AccountOut(BaseModel):
    """Data akun untuk kartu & form halaman Profil."""

    id: int
    name: str
    email: EmailStr
    phone: str | None = None
    role: UserRole
    created_at: datetime
    notifications_enabled: bool = True


class AccountUpdateRequest(BaseModel):
    """Ubah data diri. Email sengaja TIDAK bisa diubah (identitas login)."""

    name: str | None = Field(default=None, min_length=3, max_length=100)
    phone: str | None = Field(default=None, max_length=30)
    notifications_enabled: bool | None = None

    @model_validator(mode="after")
    def _validate(self) -> "AccountUpdateRequest":
        self.phone = _validate_phone(self.phone)
        return self


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> "PasswordChangeRequest":
        if not any(char.isalpha() for char in self.new_password) or not any(
            char.isdigit() for char in self.new_password
        ):
            raise ValueError("Password baru harus memuat huruf dan angka.")
        if self.confirm_password is not None and self.confirm_password != self.new_password:
            raise ValueError("Konfirmasi password tidak sama.")
        if self.new_password == self.current_password:
            raise ValueError("Password baru tidak boleh sama dengan password lama.")
        return self

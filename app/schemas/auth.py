"""Skema Pydantic untuk autentikasi & registrasi (FR-01)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models.user import UserRole


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

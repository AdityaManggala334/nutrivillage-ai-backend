-- NutriVillage AI — Skema Fase 1 (Auth + SPPG MBG)
-- Target: MySQL 8 / MariaDB 10.4 (XAMPP). Engine InnoDB, utf8mb4.
-- Catatan: tabel lain pada PDM SKPL V4 Final (profiles, ingredients, dst.)
-- ditambahkan pada fase berikutnya.

CREATE DATABASE IF NOT EXISTS `nutri_village_ai`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `nutri_village_ai`;

-- Akun pengguna: masyarakat, petugas SPPG MBG, admin, tamu.
CREATE TABLE IF NOT EXISTS `users` (
  `id`            INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `name`          VARCHAR(100) NOT NULL,
  `email`         VARCHAR(150) NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `role`          ENUM('user','petugas_sppg','admin','guest') NOT NULL DEFAULT 'user',
  `is_active`     TINYINT(1) NOT NULL DEFAULT 1,
  `created_at`    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_users_email` (`email`),
  KEY `idx_users_role` (`role`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Profil petugas SPPG MBG (relasi 1:1 dengan users).
CREATE TABLE IF NOT EXISTS `sppg_officers` (
  `id`         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id`    INT UNSIGNED NOT NULL,
  `nip`        VARCHAR(50) NOT NULL,
  `sppg_unit`  VARCHAR(150) NOT NULL,
  `region`     VARCHAR(100) NOT NULL,
  `position`   VARCHAR(100) NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_sppg_user` (`user_id`),
  UNIQUE KEY `uq_sppg_nip` (`nip`),
  CONSTRAINT `fk_sppg_user` FOREIGN KEY (`user_id`)
    REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Sekolah yang dikelola petugas SPPG MBG (1 petugas : N sekolah).
CREATE TABLE IF NOT EXISTS `schools` (
  `id`              INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `sppg_officer_id` INT UNSIGNED NOT NULL,
  `name`            VARCHAR(150) NOT NULL,
  `npsn`            VARCHAR(20)  NULL,
  `address`         VARCHAR(255) NULL,
  `region`          VARCHAR(100) NOT NULL,
  `is_active`       TINYINT(1)   NOT NULL DEFAULT 1,
  `created_at`      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_schools_officer` (`sppg_officer_id`),
  KEY `idx_schools_npsn` (`npsn`),
  CONSTRAINT `fk_schools_officer` FOREIGN KEY (`sppg_officer_id`)
    REFERENCES `sppg_officers` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Kelompok penerima manfaat per sekolah (mis. SD 1-3, SD 4-6, SMP, SMA).
CREATE TABLE IF NOT EXISTS `beneficiary_groups` (
  `id`                  INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `school_id`           INT UNSIGNED NOT NULL,
  `level`               ENUM('sd_1_3','sd_4_6','smp','sma','lainnya') NOT NULL,
  `label`               VARCHAR(100) NULL,
  `student_count`       INT UNSIGNED NOT NULL DEFAULT 0,
  `budget_per_portion`  DECIMAL(12,2) NULL,
  `created_at`          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_groups_school` (`school_id`),
  CONSTRAINT `fk_groups_school` FOREIGN KEY (`school_id`)
    REFERENCES `schools` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Kebijakan batas anggaran bahan pangan per porsi (NULL = belum dikonfigurasi).
CREATE TABLE IF NOT EXISTS `budget_policies` (
  `id`                  INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `scope`               VARCHAR(50) NOT NULL,
  `label`               VARCHAR(120) NOT NULL,
  `amount_per_portion`  DECIMAL(12,2) NULL,
  `source`              VARCHAR(255) NULL,
  `verified`            TINYINT(1) NOT NULL DEFAULT 0,
  `effective_date`      DATE NULL,
  `updated_at`          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_budget_scope` (`scope`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

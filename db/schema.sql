-- NutriVillage AI — Skema Basis Data (MySQL 8 / TiDB)
--
-- DIHASILKAN OTOMATIS dari model SQLAlchemy (scripts/export_schema.py).
-- Jangan diedit manual; ubah model di app/models/ lalu jalankan ulang skrip.
--
-- Sumber acuan: SKPL V4 Final (PDM Tabel 6.3-6.24) + ekstensi aplikasi web.


CREATE TABLE articles (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	code VARCHAR(64), 
	title VARCHAR(200) NOT NULL, 
	excerpt VARCHAR(255) NOT NULL, 
	category ENUM('Gizi Dasar','Pangan Lokal','Tips Hemat','Kesehatan') NOT NULL, 
	read_minutes INTEGER NOT NULL DEFAULT '3', 
	body JSON NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (code)
);

CREATE TABLE budget_policies (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	scope VARCHAR(50) NOT NULL, 
	label VARCHAR(120) NOT NULL, 
	amount_per_portion NUMERIC(12, 2), 
	source VARCHAR(255), 
	verified BOOL NOT NULL, 
	effective_date DATE, 
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_budget_policies_scope ON budget_policies (scope);

CREATE TABLE food_safety_info (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	code VARCHAR(64), 
	topic VARCHAR(100) NOT NULL, 
	risk_type VARCHAR(100) NOT NULL, 
	hazard TEXT NOT NULL, 
	handling TEXT NOT NULL, 
	source VARCHAR(150) NOT NULL, 
	verification ENUM('pending','verified','rejected') NOT NULL DEFAULT 'pending', 
	PRIMARY KEY (id), 
	UNIQUE (code)
);

CREATE TABLE ingredients (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	code VARCHAR(64), 
	name VARCHAR(100) NOT NULL, 
	category ENUM('Pokok','Protein','Sayur','Buah','Bumbu','Susu','Lainnya') NOT NULL, 
	unit VARCHAR(20) NOT NULL DEFAULT 'kg', 
	description TEXT, 
	image_url VARCHAR(255), 
	is_local BOOL NOT NULL DEFAULT '0', 
	is_in_season BOOL NOT NULL DEFAULT '0', 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (code)
);

CREATE TABLE recipes (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	code VARCHAR(64), 
	name VARCHAR(100) NOT NULL, 
	category ENUM('Makanan Utama','Sayur','Lauk','Berkuah','Camilan','Minuman') NOT NULL DEFAULT 'Makanan Utama', 
	description TEXT, 
	servings INTEGER NOT NULL DEFAULT '4', 
	cooking_time_min INTEGER NOT NULL DEFAULT '30', 
	image_url VARCHAR(255), 
	steps JSON NOT NULL, 
	is_vegetarian BOOL NOT NULL DEFAULT '0', 
	estimated_cost NUMERIC(12, 2) NOT NULL DEFAULT '0', 
	tags JSON NOT NULL, 
	image_key VARCHAR(50), 
	image_alt VARCHAR(255), 
	is_local BOOL NOT NULL DEFAULT '0', 
	in_season BOOL NOT NULL DEFAULT '0', 
	price_updated_at DATETIME, 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (code)
);

CREATE TABLE regions (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(100) NOT NULL, 
	province VARCHAR(100) NOT NULL DEFAULT 'Jawa Timur', 
	PRIMARY KEY (id), 
	UNIQUE (name)
);

CREATE TABLE scraper_runs (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	source VARCHAR(150) NOT NULL, 
	scheduled_at DATETIME, 
	started_at DATETIME, 
	finished_at DATETIME, 
	status ENUM('success','partial','failed') NOT NULL DEFAULT 'failed', 
	items_count INTEGER NOT NULL DEFAULT '0', 
	error_message TEXT, 
	PRIMARY KEY (id)
);

CREATE TABLE system_config (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	config_key VARCHAR(50) NOT NULL, 
	config_value NUMERIC(4, 3) NOT NULL, 
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (config_key)
);

CREATE TABLE users (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(100) NOT NULL, 
	email VARCHAR(150) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	`role` ENUM('user','petugas_sppg','admin','guest') NOT NULL, 
	is_active BOOL NOT NULL DEFAULT '1', 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_users_role ON users (`role`);

CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE TABLE family_members (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	name VARCHAR(100), 
	age INTEGER NOT NULL, 
	age_group ENUM('balita','anak','dewasa','lansia'), 
	gender ENUM('laki-laki','perempuan'), 
	weight_kg NUMERIC(5, 1) NOT NULL, 
	activity_level ENUM('rendah','sedang','tinggi') NOT NULL DEFAULT 'sedang', 
	allergies VARCHAR(255), 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_family_members_user_id ON family_members (user_id);

CREATE TABLE favorites (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	recipe_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(recipe_id) REFERENCES recipes (id) ON DELETE CASCADE
);

CREATE INDEX ix_favorites_recipe_id ON favorites (recipe_id);

CREATE INDEX ix_favorites_user_id ON favorites (user_id);

CREATE TABLE local_availability (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	ingredient_id INTEGER NOT NULL, 
	region_id INTEGER NOT NULL, 
	level ENUM('abundant','available','limited') NOT NULL DEFAULT 'available', 
	source VARCHAR(150), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_local_ingredient_region UNIQUE (ingredient_id, region_id), 
	FOREIGN KEY(ingredient_id) REFERENCES ingredients (id) ON DELETE CASCADE, 
	FOREIGN KEY(region_id) REFERENCES regions (id) ON DELETE CASCADE
);

CREATE INDEX ix_local_availability_region_id ON local_availability (region_id);

CREATE INDEX ix_local_availability_ingredient_id ON local_availability (ingredient_id);

CREATE TABLE meal_plans (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER, 
	recipe_id INTEGER, 
	day_of_week ENUM('senin','selasa','rabu','kamis','jumat','sabtu','minggu') NOT NULL, 
	meal_type ENUM('sarapan','makan-siang','makan-malam') NOT NULL, 
	week_id VARCHAR(50), 
	note VARCHAR(255), 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(recipe_id) REFERENCES recipes (id) ON DELETE SET NULL
);

CREATE INDEX ix_meal_plans_user_id ON meal_plans (user_id);

CREATE TABLE notifications (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	code VARCHAR(64), 
	user_id INTEGER, 
	title VARCHAR(150) NOT NULL, 
	message VARCHAR(500) NOT NULL, 
	kind ENUM('info','success','warning') NOT NULL DEFAULT 'info', 
	`read` BOOL NOT NULL DEFAULT '0', 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (code), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_notifications_user_id ON notifications (user_id);

CREATE TABLE nutrition_facts (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	ingredient_id INTEGER NOT NULL, 
	calories NUMERIC(8, 1) NOT NULL DEFAULT '0', 
	protein NUMERIC(8, 1) NOT NULL DEFAULT '0', 
	carbs NUMERIC(8, 1) NOT NULL DEFAULT '0', 
	fat NUMERIC(8, 1) NOT NULL DEFAULT '0', 
	fiber NUMERIC(8, 1) NOT NULL DEFAULT '0', 
	source VARCHAR(100) NOT NULL DEFAULT 'TKPI Kemenkes RI', 
	PRIMARY KEY (id), 
	UNIQUE (ingredient_id), 
	FOREIGN KEY(ingredient_id) REFERENCES ingredients (id) ON DELETE CASCADE
);

CREATE TABLE prices (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	ingredient_id INTEGER NOT NULL, 
	region_id INTEGER, 
	price NUMERIC(12, 2) NOT NULL, 
	unit VARCHAR(20) NOT NULL DEFAULT 'kg', 
	recorded_date DATE NOT NULL DEFAULT CURRENT_DATE, 
	source_type ENUM('scraper','manual') NOT NULL, 
	source VARCHAR(150) NOT NULL, 
	status ENUM('pending','approved','rejected') NOT NULL DEFAULT 'pending', 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(ingredient_id) REFERENCES ingredients (id) ON DELETE CASCADE, 
	FOREIGN KEY(region_id) REFERENCES regions (id) ON DELETE SET NULL
);

CREATE INDEX ix_prices_lookup ON prices (ingredient_id, region_id, recorded_date);

CREATE INDEX ix_prices_region_id ON prices (region_id);

CREATE INDEX ix_prices_ingredient_id ON prices (ingredient_id);

CREATE TABLE profiles (
	user_id INTEGER NOT NULL, 
	daily_budget NUMERIC(12, 2) NOT NULL, 
	adults_count INTEGER NOT NULL DEFAULT '0', 
	children_count INTEGER NOT NULL DEFAULT '0', 
	toddlers_count INTEGER NOT NULL DEFAULT '0', 
	elderly_count INTEGER NOT NULL DEFAULT '0', 
	family_count INTEGER GENERATED ALWAYS AS (adults_count + children_count + toddlers_count + elderly_count) STORED NOT NULL, 
	region_id INTEGER, 
	preferences JSON NOT NULL, 
	avoided_ingredients JSON NOT NULL, 
	onboarded BOOL NOT NULL DEFAULT '0', 
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(region_id) REFERENCES regions (id) ON DELETE SET NULL
);

CREATE TABLE recipe_ingredients (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	recipe_id INTEGER NOT NULL, 
	ingredient_id INTEGER, 
	name VARCHAR(100) NOT NULL, 
	quantity NUMERIC(10, 3) NOT NULL, 
	unit VARCHAR(20) NOT NULL DEFAULT 'kg', 
	estimated_price NUMERIC(12, 2) NOT NULL DEFAULT '0', 
	is_pantry BOOL NOT NULL DEFAULT '0', 
	note VARCHAR(100), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_recipe_ingredient UNIQUE (recipe_id, ingredient_id), 
	FOREIGN KEY(recipe_id) REFERENCES recipes (id) ON DELETE CASCADE, 
	FOREIGN KEY(ingredient_id) REFERENCES ingredients (id) ON DELETE SET NULL
);

CREATE INDEX ix_recipe_ingredients_ingredient_id ON recipe_ingredients (ingredient_id);

CREATE INDEX ix_recipe_ingredients_recipe_id ON recipe_ingredients (recipe_id);

CREATE TABLE recipe_nutrition (
	recipe_id INTEGER NOT NULL, 
	calories NUMERIC(8, 1) NOT NULL DEFAULT '0', 
	protein NUMERIC(8, 1) NOT NULL DEFAULT '0', 
	carbohydrates NUMERIC(8, 1) NOT NULL DEFAULT '0', 
	fat NUMERIC(8, 1) NOT NULL DEFAULT '0', 
	fiber NUMERIC(8, 1) NOT NULL DEFAULT '0', 
	PRIMARY KEY (recipe_id), 
	FOREIGN KEY(recipe_id) REFERENCES recipes (id) ON DELETE CASCADE
);

CREATE TABLE recommendations (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER, 
	budget NUMERIC(12, 2) NOT NULL, 
	family_count INTEGER NOT NULL, 
	region_id INTEGER, 
	month INTEGER NOT NULL, 
	status VARCHAR(20) NOT NULL DEFAULT 'completed', 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(region_id) REFERENCES regions (id) ON DELETE SET NULL
);

CREATE INDEX ix_recommendations_user_id ON recommendations (user_id);

CREATE TABLE seasonal_availability (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	ingredient_id INTEGER NOT NULL, 
	month INTEGER NOT NULL, 
	status ENUM('in_season','shoulder','off_season') NOT NULL DEFAULT 'in_season', 
	PRIMARY KEY (id), 
	CONSTRAINT uq_seasonal_ingredient_month UNIQUE (ingredient_id, month), 
	FOREIGN KEY(ingredient_id) REFERENCES ingredients (id) ON DELETE CASCADE
);

CREATE INDEX ix_seasonal_availability_ingredient_id ON seasonal_availability (ingredient_id);

CREATE TABLE sppg_officers (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	nip VARCHAR(50) NOT NULL, 
	sppg_unit VARCHAR(150) NOT NULL, 
	region VARCHAR(100) NOT NULL, 
	position VARCHAR(100), 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX ix_sppg_officers_nip ON sppg_officers (nip);

CREATE TABLE llm_explanations (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	recommendation_id INTEGER, 
	recipe_id INTEGER, 
	explanation_text TEXT NOT NULL, 
	model VARCHAR(100), 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(recommendation_id) REFERENCES recommendations (id) ON DELETE CASCADE, 
	FOREIGN KEY(recipe_id) REFERENCES recipes (id) ON DELETE CASCADE
);

CREATE INDEX ix_llm_explanations_recommendation_id ON llm_explanations (recommendation_id);

CREATE TABLE price_history (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	price_id INTEGER, 
	ingredient_id INTEGER NOT NULL, 
	region_id INTEGER, 
	price NUMERIC(12, 2) NOT NULL, 
	unit VARCHAR(20) NOT NULL DEFAULT 'kg', 
	recorded_date DATE NOT NULL, 
	source VARCHAR(150) NOT NULL, 
	source_type ENUM('scraper','manual') NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	action VARCHAR(30) NOT NULL, 
	changed_by INTEGER, 
	changed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(price_id) REFERENCES prices (id) ON DELETE SET NULL, 
	FOREIGN KEY(ingredient_id) REFERENCES ingredients (id) ON DELETE CASCADE, 
	FOREIGN KEY(region_id) REFERENCES regions (id) ON DELETE SET NULL, 
	FOREIGN KEY(changed_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_price_history_price_id ON price_history (price_id);

CREATE INDEX ix_price_history_ingredient_id ON price_history (ingredient_id);

CREATE TABLE price_verifications (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	price_id INTEGER NOT NULL, 
	admin_id INTEGER, 
	status ENUM('approved','rejected') NOT NULL, 
	note VARCHAR(255), 
	verified_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(price_id) REFERENCES prices (id) ON DELETE CASCADE, 
	FOREIGN KEY(admin_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_price_verifications_price_id ON price_verifications (price_id);

CREATE TABLE recommendation_items (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	recommendation_id INTEGER NOT NULL, 
	recipe_id INTEGER NOT NULL, 
	score_nutrition NUMERIC(5, 2) NOT NULL DEFAULT '0', 
	score_budget NUMERIC(5, 2) NOT NULL DEFAULT '0', 
	score_seasonal NUMERIC(5, 2) NOT NULL DEFAULT '0', 
	score_local NUMERIC(5, 2) NOT NULL DEFAULT '0', 
	score_total NUMERIC(5, 2) NOT NULL DEFAULT '0', 
	estimated_cost NUMERIC(12, 2) NOT NULL DEFAULT '0', 
	`rank` INTEGER NOT NULL, 
	is_selected BOOL NOT NULL DEFAULT '0', 
	PRIMARY KEY (id), 
	FOREIGN KEY(recommendation_id) REFERENCES recommendations (id) ON DELETE CASCADE, 
	FOREIGN KEY(recipe_id) REFERENCES recipes (id) ON DELETE CASCADE
);

CREATE INDEX ix_recommendation_items_recommendation_id ON recommendation_items (recommendation_id);

CREATE TABLE schools (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	sppg_officer_id INTEGER NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	npsn VARCHAR(20), 
	address VARCHAR(255), 
	region VARCHAR(100) NOT NULL, 
	is_active BOOL NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(sppg_officer_id) REFERENCES sppg_officers (id) ON DELETE CASCADE
);

CREATE INDEX ix_schools_npsn ON schools (npsn);

CREATE INDEX ix_schools_sppg_officer_id ON schools (sppg_officer_id);

CREATE TABLE shopping_lists (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER, 
	meal_plan_id INTEGER, 
	title VARCHAR(150) NOT NULL DEFAULT 'Belanja hari ini', 
	total_estimate NUMERIC(12, 2) NOT NULL DEFAULT '0', 
	notes TEXT, 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(meal_plan_id) REFERENCES meal_plans (id) ON DELETE SET NULL
);

CREATE INDEX ix_shopping_lists_user_id ON shopping_lists (user_id);

CREATE TABLE beneficiary_groups (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	school_id INTEGER NOT NULL, 
	level ENUM('sd_1_3','sd_4_6','smp','sma','lainnya') NOT NULL, 
	label VARCHAR(100), 
	student_count INTEGER NOT NULL, 
	budget_per_portion NUMERIC(12, 2), 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id) ON DELETE CASCADE
);

CREATE INDEX ix_beneficiary_groups_school_id ON beneficiary_groups (school_id);

CREATE TABLE shopping_list_items (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	list_id INTEGER NOT NULL, 
	ingredient_id INTEGER, 
	name VARCHAR(100) NOT NULL, 
	quantity NUMERIC(10, 3) NOT NULL DEFAULT '1', 
	unit VARCHAR(20) NOT NULL DEFAULT 'kg', 
	estimated_price NUMERIC(12, 2) NOT NULL DEFAULT '0', 
	checked BOOL NOT NULL DEFAULT '0', 
	PRIMARY KEY (id), 
	FOREIGN KEY(list_id) REFERENCES shopping_lists (id) ON DELETE CASCADE, 
	FOREIGN KEY(ingredient_id) REFERENCES ingredients (id) ON DELETE SET NULL
);

CREATE INDEX ix_shopping_list_items_list_id ON shopping_list_items (list_id);

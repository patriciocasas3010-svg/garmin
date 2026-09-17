-- Esquema de Postgres (Supabase) que reemplaza a la hoja de Google como
-- almacenamiento de AURA -- una tabla por pestaña que existía ahí.
--
-- Dos patrones de tabla, igual que en la hoja de Google:
--   - "snapshot" (un renglón por paciente, se sobreescribe): resumen,
--     enfoque, libre_vinculo, tokens_garmin, usuarios -- UNIQUE(nombre) o
--     UNIQUE(usuario) + upsert con "INSERT ... ON CONFLICT DO UPDATE".
--   - "historial" (se va acumulando, nunca se sobreescribe): notas,
--     inbody, antropometria, estudios, feedback -- BIGSERIAL + siempre
--     INSERT, nunca UPDATE.
--   - calorias es historial pero con upsert por (nombre, fecha): un
--     renglón por día, se corrige si ya existía ese mismo día.
--
-- A diferencia de la hoja de Google, aquí el upsert es atómico (una sola
-- instrucción SQL) -- en gspread, "buscar la fila y actualizar o agregar"
-- eran 2 llamadas separadas (leer todo, decidir, escribir), con una
-- ventana real donde dos nutriólogas guardando al mismo paciente al mismo
-- tiempo podían pisarse una a la otra. Con ON CONFLICT eso ya no puede
-- pasar, lo resuelve la base de datos misma.

CREATE TABLE IF NOT EXISTS resumen (
    nombre TEXT PRIMARY KEY,
    fecha TEXT,
    calificacion NUMERIC,
    recuperacion NUMERIC,
    sueno NUMERIC,
    actividad NUMERIC,
    dias_con_actividad NUMERIC,
    dias_sin_actividad NUMERIC,
    rhr_7d NUMERIC,
    datos JSONB,
    fuente TEXT
);

CREATE TABLE IF NOT EXISTS enfoque (
    nombre TEXT PRIMARY KEY,
    enfoque TEXT,
    meta_grasa_pct NUMERIC,
    dias_plan_mes NUMERIC,
    condicion_metabolica TEXT,
    glp1_molecula TEXT,
    glp1_dosis TEXT,
    glp1_fecha_inicio TEXT,
    nutriologo TEXT,
    fecha TEXT
);

CREATE TABLE IF NOT EXISTS notas (
    id BIGSERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    fecha TEXT,
    nota TEXT
);
CREATE INDEX IF NOT EXISTS notas_nombre_idx ON notas (nombre);

CREATE TABLE IF NOT EXISTS inbody (
    id BIGSERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    fecha TEXT,
    modelo TEXT,
    altura_cm NUMERIC,
    edad NUMERIC,
    sexo TEXT,
    peso_kg NUMERIC,
    masa_grasa_kg NUMERIC,
    mme_kg NUMERIC,
    grasa_visceral NUMERIC,
    agua_total_l NUMERIC,
    agua_intra_l NUMERIC,
    agua_extra_l NUMERIC,
    imc NUMERIC,
    pgc_pct NUMERIC,
    bmr_kcal NUMERIC
);
CREATE INDEX IF NOT EXISTS inbody_nombre_idx ON inbody (nombre);

CREATE TABLE IF NOT EXISTS antropometria (
    id BIGSERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    fecha TEXT,
    grasa_faulkner_pct NUMERIC,
    grasa_calculado_kg NUMERIC,
    pliegue_supraespinal_mm NUMERIC,
    pliegue_muslo_frontal_mm NUMERIC,
    pliegue_pantorrilla_medial_mm NUMERIC,
    pliegue_abdominal_mm NUMERIC,
    pliegue_tricipital_mm NUMERIC,
    pliegue_subescapular_mm NUMERIC,
    pliegue_suprailiaco_mm NUMERIC,
    pliegue_bicipital_mm NUMERIC,
    circ_cadera_cm NUMERIC,
    circ_pantorrilla_cm NUMERIC,
    circ_muslo_medio_cm NUMERIC,
    circ_brazo_contraido_cm NUMERIC,
    circ_cintura_cm NUMERIC,
    circ_brazo_relajado_cm NUMERIC,
    circ_muslo_cm NUMERIC
);
CREATE INDEX IF NOT EXISTS antropometria_nombre_idx ON antropometria (nombre);

-- fecha es DATE real (a diferencia del resto de las tablas, que guardan
-- "Fecha" como TEXT "dd.mm.aaaa" igual que la hoja de Google, para no
-- tocar el resto del código) porque aquí sí se ordena directamente por
-- fecha para la gráfica de calorías en el tiempo -- un ORDER BY sobre
-- texto "dd.mm.aaaa" ordenaría alfabéticamente, no cronológicamente
-- (enero quedaría antes que noviembre del año anterior).
CREATE TABLE IF NOT EXISTS calorias (
    nombre TEXT NOT NULL,
    fecha DATE NOT NULL,
    calorias_comidas NUMERIC,
    PRIMARY KEY (nombre, fecha)
);

CREATE TABLE IF NOT EXISTS estudios (
    id BIGSERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    fecha TEXT,
    laboratorio TEXT,
    resultados JSONB
);
CREATE INDEX IF NOT EXISTS estudios_nombre_idx ON estudios (nombre);

CREATE TABLE IF NOT EXISTS libre_vinculo (
    nombre TEXT PRIMARY KEY,
    libre_patient_id TEXT,
    libre_patient_nombre TEXT
);

CREATE TABLE IF NOT EXISTS usuarios (
    usuario TEXT PRIMARY KEY,
    nombre TEXT,
    password_hash TEXT,
    salt TEXT,
    rol TEXT,
    fecha TEXT
);

CREATE TABLE IF NOT EXISTS feedback (
    id BIGSERIAL PRIMARY KEY,
    fecha TEXT,
    usuario TEXT,
    paciente TEXT,
    mensaje TEXT
);

CREATE TABLE IF NOT EXISTS tokens_garmin (
    nombre TEXT PRIMARY KEY,
    token TEXT,
    fecha_guardado TEXT,
    clave_conexion TEXT
);

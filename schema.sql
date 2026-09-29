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
    fecha TEXT,
    -- Tope de análisis con IA al mes para este nutriólogo -- NULL usa el
    -- default global (ver analisis_ia_store.LIMITE_DEFAULT). Claude lo
    -- paga AURA de forma centralizada, así que cada usuario tiene un
    -- número definido de interacciones, no acceso ilimitado.
    limite_analisis_mes INTEGER
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

-- Oura dejó de permitir Personal Access Tokens en diciembre de 2025 --
-- ahora es OAuth2 (ver oura_store.py/conectar_oura_web.py), con el mismo
-- mecanismo de clave_conexion de un solo uso que tokens_garmin, que aquí
-- también sirve como el "state" que Oura regresa intacto al autorizar.
-- access_token/refresh_token reemplazan al "token" simple de antes
-- (expira_en permite refrescar solo, sin que el paciente vuelva a
-- autorizar nada).
-- "Cerebro científico" de AURA -- el objetivo es que las reglas y su
-- justificación vivan en la base de datos, no solo dentro del código de
-- cruces_clinicos.py (donde hoy están, correctas pero sin rastro de
-- "por qué" ni forma de que un nutriólogo las consulte). Esto NO
-- reemplaza los 10 paneles que ya están probados y en producción -- es
-- la capa de trazabilidad/evidencia que se les puede ir conectando
-- encima, sin tocar la lógica que ya funciona antes del lanzamiento.

-- Capa 1: de dónde sale cada regla (guía clínica, estudio, consenso).
CREATE TABLE IF NOT EXISTS evidencia_clinica (
    id BIGSERIAL PRIMARY KEY,
    fuente TEXT NOT NULL,
    tipo TEXT,
    poblacion TEXT,
    nivel_evidencia TEXT,
    url TEXT,
    fecha_publicacion DATE,
    notas TEXT
);

-- Capa 2: reglas como dato, no como código -- para reglas NUEVAS que se
-- vayan agregando de aquí en adelante (los 10 paneles actuales de
-- cruces_clinicos.py se quedan como están; migrarlos aquí es un
-- proyecto aparte, después del lanzamiento).
CREATE TABLE IF NOT EXISTS reglas_clinicas (
    id BIGSERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    marcador TEXT,
    condicion TEXT,
    contexto TEXT,
    interpretacion TEXT,
    recomendacion TEXT,
    evidencia_id BIGINT REFERENCES evidencia_clinica(id),
    estado TEXT DEFAULT 'borrador',
    version INT DEFAULT 1,
    fecha_revision DATE
);

-- Capa 3: trazabilidad -- cada vez que se le muestra al nutriólogo una
-- recomendación (venga de un panel fijo o de una regla de arriba), se
-- guarda qué datos la dispararon. Así "¿por qué AURA muestra esto?"
-- siempre tiene una respuesta consultable, no solo la salida de un LLM.
CREATE TABLE IF NOT EXISTS recomendaciones_generadas (
    id BIGSERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    fecha TIMESTAMPTZ DEFAULT now(),
    panel TEXT,
    regla_id BIGINT REFERENCES reglas_clinicas(id),
    datos_usados JSONB,
    texto TEXT,
    version_sistema TEXT,
    revisado_por TEXT,
    fecha_revision TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS recomendaciones_nombre_idx ON recomendaciones_generadas (nombre);

-- Cuota de análisis con IA por nutriólogo -- un renglón por cada vez que
-- alguien le da clic a "Generar análisis" (ver analisis_ia_store.py).
-- Sirve para contar cuántos lleva cada quien este mes y frenarlo si pasa
-- su límite (usuarios.limite_analisis_mes) -- Claude lo paga AURA de
-- forma centralizada, no cada nutriólogo, así que el control de gasto
-- tiene que vivir aquí.
CREATE TABLE IF NOT EXISTS uso_analisis_ia (
    id BIGSERIAL PRIMARY KEY,
    usuario TEXT NOT NULL,
    paciente TEXT NOT NULL,
    fecha TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS uso_analisis_ia_usuario_idx ON uso_analisis_ia (usuario);

-- AURA Recipes -- capa de EJECUCIÓN, no la biblioteca de 30,000 recetas
-- de un competidor: arranca chica (100-300 recetas reales, revisadas por
-- un nutriólogo antes de "aprobada") y vive conectada al cerebro
-- científico de arriba, no suelta. Cada receta puede citar por qué se
-- recomienda (evidencia_id) y quedar ligada a la recomendación exacta
-- que la sugirió (recomendaciones_generadas), para que "por qué le
-- dieron esto a este paciente" siempre sea trazable.
CREATE TABLE IF NOT EXISTS recetas (
    id BIGSERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    ingredientes JSONB,             -- [{"item":"pechuga de pollo","cantidad":150,"unidad":"g"}, ...]
    kcal NUMERIC,
    proteina_g NUMERIC,
    carbohidratos_g NUMERIC,
    grasa_g NUMERIC,
    fibra_g NUMERIC,
    sodio_mg NUMERIC,
    tiempo_prep_min NUMERIC,
    dificultad TEXT,                -- facil / media / dificil
    costo_aprox TEXT,               -- bajo / medio / alto
    tipo_comida TEXT,               -- desayuno / comida / cena / snack
    cocina TEXT,                    -- mexicana / mediterranea / asiatica / ...
    tags_clinicos TEXT[],           -- {diabetes, renal, hipertension, ...}
    tags_deportivos TEXT[],         -- {alto_en_proteina, pre_entreno, ...}
    tags_conductuales TEXT[],       -- {rapido, batch_cooking, bajo_presupuesto, ...}
    tags_culturales TEXT[],         -- {vegetariano, sin_gluten, halal, ...}
    sustituciones JSONB,            -- [{"de":"arroz blanco","por":"arroz integral","razon":"..."}]
    fuente TEXT,
    version INT DEFAULT 1,
    evidencia_id BIGINT REFERENCES evidencia_clinica(id),
    estado TEXT DEFAULT 'borrador', -- nunca sale a un paciente sin que un nutriólogo la revise y la pase a "aprobada"
    fecha_revision DATE
);
CREATE INDEX IF NOT EXISTS recetas_tags_clinicos_idx ON recetas USING GIN (tags_clinicos);
CREATE INDEX IF NOT EXISTS recetas_tags_culturales_idx ON recetas USING GIN (tags_culturales);
CREATE INDEX IF NOT EXISTS recetas_tags_conductuales_idx ON recetas USING GIN (tags_conductuales);

-- El plan en sí: macros objetivo (sugeridos por plan_nutricional.py,
-- editables por el nutriólogo antes de crear el plan) + estado de
-- aprobación. Nunca sale a un paciente en "borrador" -- necesita que el
-- nutriólogo le dé "Aprobar" explícitamente (ver planes_store.py).
CREATE TABLE IF NOT EXISTS planes_nutricionales (
    id BIGSERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    fecha TIMESTAMPTZ DEFAULT now(),
    kcal_objetivo NUMERIC,
    proteina_g_objetivo NUMERIC,
    carbohidratos_g_objetivo NUMERIC,
    grasa_g_objetivo NUMERIC,
    notas TEXT,
    -- Menú día por día de las 2 semanas (markdown), generado por
    -- plan_generador.py -- NULL cuando el plan se creó solo con
    -- macros/recetas, sin pedirle a Claude el menú completo.
    contenido TEXT,
    estado TEXT DEFAULT 'borrador',
    creado_por TEXT,
    aprobado_por TEXT,
    fecha_aprobacion TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS planes_nutricionales_nombre_idx ON planes_nutricionales (nombre);

-- Qué receta se le asignó a qué paciente y por qué (liga a la
-- recomendación que la sugirió cuando aplica -- puede ser NULL si el
-- nutriólogo la agregó a mano, sin pasar por una recomendación de AURA).
-- plan_id liga esta fila al plan completo (planes_nutricionales) del que
-- forma parte -- NULL para recetas sueltas asignadas fuera de un plan.
CREATE TABLE IF NOT EXISTS plan_recetas (
    id BIGSERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    receta_id BIGINT REFERENCES recetas(id),
    fecha_asignada TIMESTAMPTZ DEFAULT now(),
    tipo_comida TEXT,
    recomendacion_id BIGINT REFERENCES recomendaciones_generadas(id),
    plan_id BIGINT REFERENCES planes_nutricionales(id),
    activa BOOLEAN DEFAULT true
);
CREATE INDEX IF NOT EXISTS plan_recetas_nombre_idx ON plan_recetas (nombre);
CREATE INDEX IF NOT EXISTS plan_recetas_plan_id_idx ON plan_recetas (plan_id);

-- El otro lado del loop: lo que el paciente reporta haber comido (foto o
-- captura manual), cruzado contra lo que el plan le asignó ese tipo de
-- comida. A propósito se llama "consumo_observado" y no "adherencia" --
-- si el paciente no registra todo lo que come, no podemos decir que
-- siguió el plan al pie de la letra, solo que lo que SÍ registró
-- coincide o no coincide con lo indicado.
CREATE TABLE IF NOT EXISTS consumo_observado (
    id BIGSERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    fecha TIMESTAMPTZ DEFAULT now(),
    plan_receta_id BIGINT REFERENCES plan_recetas(id),
    foto_url TEXT,
    descripcion_detectada TEXT,
    kcal_estimadas NUMERIC,
    coincide_con_plan BOOLEAN,
    notas TEXT
);
CREATE INDEX IF NOT EXISTS consumo_observado_nombre_idx ON consumo_observado (nombre);

CREATE TABLE IF NOT EXISTS tokens_oura (
    nombre TEXT PRIMARY KEY,
    access_token TEXT,
    refresh_token TEXT,
    expira_en TIMESTAMPTZ,
    fecha_guardado TEXT,
    clave_conexion TEXT
);

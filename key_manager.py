services:
  # ── 1. THE DASHBOARD (UI) ──────────────────────────────────────────────────
  - type: web
    name: builder-ui
    runtime: python
    plan: starter
    buildCommand: pip install -r requirements-ui.txt
    startCommand: streamlit run app.py --server.port $PORT --server.address 0.0.0.0
    envVars:
      - key: AUTH_SERVICE_URL
        fromService:
          type: web
          name: builder-auth
          envVarKey: RENDER_INTERNAL_HOSTNAME
      - key: AI_SERVICE_URL
        fromService:
          type: web
          name: builder-ai
          envVarKey: RENDER_INTERNAL_HOSTNAME
      - key: BILLING_SERVICE_URL
        fromService:
          type: web
          name: builder-billing
          envVarKey: RENDER_INTERNAL_HOSTNAME
      - key: ANALYTICS_SERVICE_URL
        fromService:
          type: web
          name: builder-analytics
          envVarKey: RENDER_INTERNAL_HOSTNAME
      - key: ADMIN_SERVICE_URL
        fromService:
          type: web
          name: builder-admin
          envVarKey: RENDER_INTERNAL_HOSTNAME
      - key: INTERNAL_API_KEY
        generateValue: true
      - key: MASTER_KEY
        sync: false
      - key: PYTHON_VERSION
        value: 3.11.7

  # ── 2. THE AI ROUND TABLE ─────────────────────────────────────────────────
  - type: web
    name: builder-ai
    runtime: python
    plan: starter
    buildCommand: pip install -r requirements-services.txt
    startCommand: uvicorn ai_service:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: INTERNAL_API_KEY
        fromService:
          type: web
          name: builder-ui
          envVarKey: INTERNAL_API_KEY
      - key: DATABASE_URL
        fromDatabase:
          name: builder-db
          property: connectionString
      - key: XAI_API_KEY
        sync: false
      - key: ANTHROPIC_API_KEY
        sync: false
      - key: GEMINI_API_KEY
        sync: false
      - key: OPENAI_API_KEY
        sync: false

  # ── 3. THE SECURITY GUARD (Auth) ─────────────────────────────────────────
  - type: web
    name: builder-auth
    runtime: python
    plan: starter
    buildCommand: pip install -r requirements-services.txt
    startCommand: uvicorn auth_service:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: INTERNAL_API_KEY
        fromService:
          type: web
          name: builder-ui
          envVarKey: INTERNAL_API_KEY
      - key: DATABASE_URL
        fromDatabase:
          name: builder-db
          property: connectionString
      - key: JWT_SECRET
        generateValue: true

  # ── 4. THE CASH REGISTER (Billing) ───────────────────────────────────────
  - type: web
    name: builder-billing
    runtime: python
    plan: starter
    buildCommand: pip install -r requirements-services.txt
    startCommand: uvicorn billing_service:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: INTERNAL_API_KEY
        fromService:
          type: web
          name: builder-ui
          envVarKey: INTERNAL_API_KEY
      - key: AUTH_SERVICE_URL
        fromService:
          type: web
          name: builder-auth
          envVarKey: RENDER_INTERNAL_HOSTNAME
      - key: STRIPE_SECRET_KEY
        sync: false
      - key: STRIPE_WEBHOOK_SEC
        sync: false
      - key: APP_URL
        sync: false

  # ── 5. THE LOGBOOK (Analytics) ────────────────────────────────────────────
  - type: web
    name: builder-analytics
    runtime: python
    plan: starter
    buildCommand: pip install -r requirements-services.txt
    startCommand: uvicorn analytics_service:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: INTERNAL_API_KEY
        fromService:
          type: web
          name: builder-ui
          envVarKey: INTERNAL_API_KEY
      - key: DATABASE_URL
        fromDatabase:
          name: builder-db
          property: connectionString

  # ── 6. THE CONTROL ROOM (Admin) ──────────────────────────────────────────
  - type: web
    name: builder-admin
    runtime: python
    plan: starter
    buildCommand: pip install -r requirements-services.txt
    startCommand: uvicorn admin_service:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: MASTER_KEY
        fromService:
          type: web
          name: builder-ui
          envVarKey: MASTER_KEY
      - key: INTERNAL_API_KEY
        fromService:
          type: web
          name: builder-ui
          envVarKey: INTERNAL_API_KEY
      - key: DATABASE_URL
        fromDatabase:
          name: builder-db
          property: connectionString
      - key: AUTH_SERVICE_URL
        fromService:
          type: web
          name: builder-auth
          envVarKey: RENDER_INTERNAL_HOSTNAME
      - key: AI_SERVICE_URL
        fromService:
          type: web
          name: builder-ai
          envVarKey: RENDER_INTERNAL_HOSTNAME

  # ── 7. THE PRINT SHOP (Export) ────────────────────────────────────────────
  - type: web
    name: builder-export
    runtime: python
    plan: starter
    buildCommand: pip install -r requirements-services.txt
    startCommand: uvicorn export_service:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: INTERNAL_API_KEY
        fromService:
          type: web
          name: builder-ui
          envVarKey: INTERNAL_API_KEY

# ── 8. THE STORAGE TANK (Database) ───────────────────────────────────────────
databases:
  - name: builder-db
    plan: basic
    postgresMajorVersion: 15

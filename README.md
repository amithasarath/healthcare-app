# Healthcare App

HIPAA-compliant Patient Management System built with FastAPI and PostgreSQL.

## Features

- RESTful API for patient management
- PostgreSQL database with SQLAlchemy ORM
- Soft deletes for HIPAA compliance (audit trail)
- Auto-generated Medical Record Numbers (MRN)
- Health check endpoint for ECS
- Docker containerization

## Project Structure

```
healthcare-app/
├── src/
│   ├── main.py           # FastAPI application
│   └── .env.example      # Environment template
├── deployment/
│   ├── dev.params.json   # Dev environment parameters
│   └── prod.params.json  # Prod environment parameters
├── .github/workflows/
│   └── deploy.yml        # CI/CD workflow
├── Dockerfile
├── requirements.txt
└── README.md
```

## Prerequisites

- Infrastructure deployed using [ekabrahmaa-infra-templates](https://github.com/YOUR_USERNAME/ekabrahmaa-infra-templates)
- AWS CLI configured
- Docker installed

## Quick Start

### 1. Deploy Infrastructure First

Clone the infra templates repo and deploy:

```bash
git clone https://github.com/YOUR_USERNAME/ekabrahmaa-infra-templates.git
cd ekabrahmaa-infra-templates

aws cloudformation create-stack \
  --stack-name healthcare-dev \
  --template-body file://minimal-hipaa-compliant/template.yml \
  --parameters file://path/to/healthcare-app/deployment/dev.params.json \
  --capabilities CAPABILITY_NAMED_IAM
```

### 2. Configure GitHub Secrets

Go to **GitHub Repo → Settings → Secrets → Actions**:

| Secret | Value |
|--------|-------|
| `AWS_ACCESS_KEY_ID` | Your AWS access key |
| `AWS_SECRET_ACCESS_KEY` | Your AWS secret key |

### 3. Push to Deploy

```bash
git checkout -b dev
git push -u origin dev
```

The workflow triggers on pushes to `dev` or `feature/*` branches.

## Local Development

### Using Docker

```bash
# Start PostgreSQL
docker run -d --name postgres \
  -e POSTGRES_USER=healthcareapp \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=healthcaredb \
  -p 5432:5432 \
  postgres:15

# Build and run app
docker build -t healthcare-app .
docker run -d --name app \
  -e DATABASE_URL=postgresql://healthcareapp:password@host.docker.internal:5432/healthcaredb \
  -p 8000:8000 \
  healthcare-app
```

### Without Docker

```bash
cd src
python -m venv venv
source venv/bin/activate
pip install -r ../requirements.txt

export DATABASE_URL=postgresql://healthcareapp:password@localhost:5432/healthcaredb
uvicorn main:app --reload --port 8000
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API info |
| GET | `/health` | Health check |
| GET | `/api/docs` | Swagger UI |
| GET | `/api/patients` | List patients |
| GET | `/api/patients/{id}` | Get patient |
| POST | `/api/patients` | Create patient |
| PUT | `/api/patients/{id}` | Update patient |
| DELETE | `/api/patients/{id}` | Soft delete patient |

## Deployment Configuration

Edit `deployment/dev.params.json` before deploying:

```json
{
  "ParameterKey": "DBPassword",
  "ParameterValue": "YOUR_SECURE_PASSWORD"
},
{
  "ParameterKey": "DefaultVpcId",
  "ParameterValue": "vpc-xxx"
}
```

**Important:** Never commit actual passwords. Use environment-specific values.

## CI/CD Workflow

The workflow (`.github/workflows/deploy.yml`):

1. Triggers on push to `dev` or `feature/*`
2. Builds Docker image
3. Pushes to ECR
4. Updates ECS task definition
5. Deploys to ECS service
6. Outputs application URL

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `ENVIRONMENT` | dev/staging/prod |
| `DB_HOST` | Database host |
| `DB_PORT` | Database port (5432) |
| `DB_NAME` | Database name |
| `DB_USER` | Database username |
| `DB_PASSWORD` | Database password |

## License

MIT

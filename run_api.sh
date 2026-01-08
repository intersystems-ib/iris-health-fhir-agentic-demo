#!/bin/bash
#
# Run the Lab Follow-up Recommendation Agent API
#
# Usage:
#   ./run_api.sh
#
# The API will be available at:
#   http://localhost:8000
#
# API Documentation (Swagger UI):
#   http://localhost:8000/docs
#
# Alternative documentation (ReDoc):
#   http://localhost:8000/redoc
#

echo "🚀 Starting Lab Follow-up Recommendation Agent API..."
echo ""
echo "API will be available at: http://localhost:8000"
echo "Swagger UI: http://localhost:8000/docs"
echo "ReDoc: http://localhost:8000/redoc"
echo ""

uvicorn clinical_ai.api:app --reload --host 0.0.0.0 --port 8000

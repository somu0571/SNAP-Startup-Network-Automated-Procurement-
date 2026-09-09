@echo off
title SNAP - Startup Network & Automated Procurement
echo ============================================================
echo   Starting SNAP GovTech Platform + AI RAG Engine
echo ============================================================
echo.
echo [1/2] Installing RAG Engine Python dependencies...
cd rag-engine
pip install -r requirements.txt -q 2>nul
cd ..
echo [2/2] Starting unified platform...
echo.
npm start
pause

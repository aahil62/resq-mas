import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.routes import experiments, health, simulation

RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "results")

app = FastAPI(title="RESQ-MAS API", description="Coordinated Multi-Agent Disaster Response Simulator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(simulation.router)
app.include_router(experiments.router)

PAPER_DIR = os.path.join(os.path.dirname(RESULTS_DIR), "paper")
if os.path.isdir(PAPER_DIR):
    app.mount("/paper", StaticFiles(directory=PAPER_DIR), name="paper")

if os.path.isdir(RESULTS_DIR):
    app.mount("/results", StaticFiles(directory=RESULTS_DIR), name="results")

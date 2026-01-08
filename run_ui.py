#!/usr/bin/env python3
"""
Launcher script for the Clinical AI Gradio UI.

Usage:
    python run_ui.py
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from clinical_ai.ui.app import create_ui

if __name__ == "__main__":
    print("=" * 80)
    print("🏥 Clinical AI Demo - Lab Follow-up Recommendation UI")
    print("=" * 80)
    print("Starting Gradio interface on http://localhost:7860")
    print("=" * 80)
    print()

    demo = create_ui()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False
    )

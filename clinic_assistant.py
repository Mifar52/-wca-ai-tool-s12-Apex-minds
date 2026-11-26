"""
Clinic FAQ Assistant - We Can Academy, AI Course, Season 12 group project.

A command-line chatbot for a (fictional) small clinic. It answers questions
about hours, services, prices and booking, remembers the whole conversation,
refuses to diagnose, and saves a summary of the session to a dated JSON file.
"""

import glob
import json
import os
from datetime import datetime

import anthropic
from dotenv import load_dotenv
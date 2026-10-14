import argparse
import os
import sys
from typing import Optional
from dotenv import load_dotenv
from google import genai
from google.genai import types

SYSTEM_PROMPT = """You are an expert Agile Delivery Lead and Technical Specification Refiner.
Your task is to refine the provided raw feature specification markdown according to strict Definition of Ready (DoR) standards and Cucumber Gherkin guidelines.

Follow these strict transformation rules:
1. Section 0 Injection:
   Inject a section `## 0. Questions & Clarification Needed for Human Sign-Off` at the very top highlighting ambiguous parameters, missing edge cases, or unstated business assumptions.

2. Advanced Gherkin Hardening (Cucumber.io Standard):
   - Evaluate user stories against official Cucumber Gherkin reference constructs (https://cucumber.io/docs/gherkin/reference/).
   - Convert basic, single-line scenarios into comprehensive acceptance criteria sets.
   - Scenario Outlines & Examples: Mandate the use of `Scenario Outline` paired with `Examples:` data tables strictly for dynamic business logic permutations and boundary value inputs.
   - Data Tables & Doc Strings: Mandate inline Gherkin `Data Tables` for complex entity inputs and step preconditions.
   - Multi-Outcome Coverage: Ensure every story includes a Happy Path scenario, a Boundary/Edge Case scenario, and an Explicit Error/Failure state.

3. Edge Case & Module Boundary Expansion:
   - Automatically insert processing logic for zero-spend states, missing reference data, and boundary limits while verifying compliance with `ARCHITECTURE.md`.

4. Clean Markdown Output:
   - Guarantee clean Markdown output without wrapping the top-level document in markdown code fences (
import json
import os
import traceback
from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import time
import concurrent.futures

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent.parent

problems_cache = None

def load_problems():
    global problems_cache
    if problems_cache is not None:
        return problems_cache
    problems = {}
    problems_dir = BASE_DIR / "problems"
    for f in sorted(problems_dir.glob("*.json")):
        with open(f) as fh:
            p = json.load(fh)
            problems[p["id"]] = p
    problems_cache = problems
    return problems

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    html_path = BASE_DIR / "templates" / "index.html"
    html_content = html_path.read_text(encoding="utf-8")
    return HTMLResponse(html_content)

@app.get("/api/problems")
async def list_problems():
    problems = load_problems()
    summary = []
    for p in problems.values():
        summary.append({"id": p["id"], "title": p["title"], "difficulty": p["difficulty"]})
    return JSONResponse(summary)

@app.get("/api/problems/{problem_id}")
async def get_problem(problem_id: str):
    problems = load_problems()
    p = problems.get(problem_id)
    if not p:
        return JSONResponse({"error": "Problem not found"}, status_code=404)
    return JSONResponse({
        "id": p["id"],
        "title": p["title"],
        "difficulty": p["difficulty"],
        "description": p["description"],
        "function_name": p["function_name"],
        "params": p["params"],
        "return_type": p["return_type"],
        "starter_code": p["starter_code"],
    })

def _run_code(code, function_name, test_cases):
    output_capture = StringIO()
    namespace = {}
    try:
        exec(code, namespace)
    except Exception as e:
        return {"error": f"Compilation error:\n{traceback.format_exc()}"}

    if function_name not in namespace:
        return {"error": f"Function '{function_name}' not defined in your code."}

    func = namespace[function_name]
    results = []
    all_passed = True

    for tc in test_cases:
        with redirect_stdout(output_capture), redirect_stderr(output_capture):
            try:
                start = time.time()
                result = func(**tc["input"])
                elapsed = round((time.time() - start) * 1000, 1)
                passed = result == tc["expected"]
                if not passed:
                    all_passed = False
                results.append({
                    "input": tc["input"],
                    "expected": tc["expected"],
                    "actual": result,
                    "passed": passed,
                    "time_ms": elapsed,
                })
            except Exception as e:
                all_passed = False
                results.append({
                    "input": tc["input"],
                    "expected": tc["expected"],
                    "actual": f"Error: {type(e).__name__}: {e}",
                    "passed": False,
                    "time_ms": None,
                })

    return {"all_passed": all_passed, "results": results, "stdout": output_capture.getvalue()}

@app.post("/api/submit")
async def submit(body: dict):
    problem_id = body.get("problem_id")
    code = body.get("code")
    if not problem_id or not code:
        return JSONResponse({"error": "Missing problem_id or code"}, status_code=400)

    problems = load_problems()
    p = problems.get(problem_id)
    if not p:
        return JSONResponse({"error": "Problem not found"}, status_code=404)

    with concurrent.futures.ThreadPoolExecutor() as pool:
        future = pool.submit(_run_code, code, p["function_name"], p["test_cases"])
        try:
            result = future.result(timeout=10)
        except concurrent.futures.TimeoutError:
            result = {"error": "Your code timed out (limit: 10 seconds)."}

    return JSONResponse(result)

@app.post("/api/run")
async def run_code(body: dict):
    code = body.get("code", "")
    if not code:
        return JSONResponse({"error": "No code provided"}, status_code=400)

    with concurrent.futures.ThreadPoolExecutor() as pool:
        def _exec():
            output_capture = StringIO()
            namespace = {}
            with redirect_stdout(output_capture), redirect_stderr(output_capture):
                try:
                    exec(code, namespace)
                except Exception:
                    return {"stdout": output_capture.getvalue(), "error": traceback.format_exc()}
            return {"stdout": output_capture.getvalue(), "error": None}
        future = pool.submit(_exec)
        try:
            result = future.result(timeout=10)
        except concurrent.futures.TimeoutError:
            result = {"stdout": "", "error": "Your code timed out (limit: 10 seconds)."}

    return JSONResponse(result)

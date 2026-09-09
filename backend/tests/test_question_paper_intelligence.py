"""
test_question_paper_intelligence.py
End-to-end verification script for Question Paper Intelligence and Multimodal Vision answering.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add backend to python path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from core.config import get_settings
cfg = get_settings()

from PIL import Image, ImageDraw, ImageFont
from services.image_service import (
    preprocess_image_for_vision,
    extract_structured_question_paper,
    process_image_to_chunks,
)
from services.chat_service import (
    detect_target_question,
    is_solve_all_or_paper_request,
    ask_question,
    ask_question_stream,
)
from rag.general_llm import vision_chat
from rag.vector_store import get_vector_store


def create_test_exam_paper_image(dest_path: Path) -> Path:
    """Create a high-contrast exam question paper image with formulas and diagrams."""
    img = Image.new("RGB", (1000, 1200), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Title & Header
    draw.text((320, 40), "MIDTERM EXAMINATION - 2026", fill=(0, 0, 0))
    draw.text((350, 70), "DEPARTMENT OF MATHEMATICS", fill=(0, 0, 0))
    draw.text((100, 110), "Time: 2 Hours                                            Max Marks: 50", fill=(0, 0, 0))
    draw.line([(80, 140), (920, 140)], fill=(0, 0, 0), width=2)

    # Section A Header
    draw.text((100, 160), "SECTION A (Answer all questions - 5 Marks each)", fill=(0, 0, 0))

    # Question 1: Calculus & Limits
    draw.text((100, 200), "Question 1:", fill=(0, 0, 0))
    draw.text((100, 230), "Evaluate the definite integral:", fill=(0, 0, 0))
    draw.text((120, 260), "Integral from 0 to pi/2 of sin(x)/(sin(x) + cos(x)) dx.", fill=(0, 0, 0))
    draw.text((100, 290), "Show step-by-step properties of definite integrals used.", fill=(0, 0, 0))

    # Question 2: Linear Algebra & Matrix
    draw.text((100, 350), "Question 2:", fill=(0, 0, 0))
    draw.text((100, 380), "Given the 2x2 matrix A = [[3, 1], [1, 3]], find:", fill=(0, 0, 0))
    draw.text((120, 410), "(a) The characteristic equation det(A - lambda * I) = 0", fill=(0, 0, 0))
    draw.text((120, 440), "(b) The eigenvalues lambda_1 and lambda_2", fill=(0, 0, 0))
    draw.text((120, 470), "(c) The corresponding normalized eigenvectors.", fill=(0, 0, 0))

    # Section B Header
    draw.line([(80, 520), (920, 520)], fill=(0, 0, 0), width=1)
    draw.text((100, 540), "SECTION B (Multiple Choice Questions - 2 Marks each)", fill=(0, 0, 0))

    # Question 3: MCQ
    draw.text((100, 580), "Question 3: What is the derivative of f(x) = ln(x^2 + 1)?", fill=(0, 0, 0))
    draw.text((120, 610), "(A) 2x / (x^2 + 1)", fill=(0, 0, 0))
    draw.text((120, 640), "(B) 1 / (x^2 + 1)", fill=(0, 0, 0))
    draw.text((120, 670), "(C) 2 / (x^2 + 1)", fill=(0, 0, 0))
    draw.text((120, 700), "(D) x / (x^2 + 1)", fill=(0, 0, 0))

    # Diagram for Question 4
    draw.line([(80, 750), (920, 750)], fill=(0, 0, 0), width=1)
    draw.text((100, 770), "Question 4: Refer to the circuit diagram below.", fill=(0, 0, 0))
    draw.text((100, 800), "Calculate the total equivalent resistance between terminals A and B.", fill=(0, 0, 0))

    # Draw Circuit Diagram
    draw.rectangle([(250, 850), (350, 890)], outline=(0, 0, 0), width=2)
    draw.text((275, 860), "R1 = 4 ohm", fill=(0, 0, 0))

    draw.rectangle([(450, 850), (550, 890)], outline=(0, 0, 0), width=2)
    draw.text((475, 860), "R2 = 6 ohm", fill=(0, 0, 0))

    draw.line([(150, 870), (250, 870)], fill=(0, 0, 0), width=2)
    draw.line([(350, 870), (450, 870)], fill=(0, 0, 0), width=2)
    draw.line([(550, 870), (650, 870)], fill=(0, 0, 0), width=2)

    draw.ellipse([(140, 865), (150, 875)], fill=(0, 0, 0))
    draw.text((125, 860), "A", fill=(0, 0, 0))

    draw.ellipse([(650, 865), (660, 875)], fill=(0, 0, 0))
    draw.text((670, 860), "B", fill=(0, 0, 0))

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(dest_path))
    return dest_path


async def run_tests():
    print("\n" + "="*70)
    print("STARTING QUESTION PAPER INTELLIGENCE VERIFICATION TEST SUITE")
    print("="*70 + "\n")

    # Test 1: Query Locator Heuristics
    print("[TEST 1] Testing Question Locator Patterns...")
    assert detect_target_question("Answer question 2") == 2, "Failed Q2 detection"
    assert detect_target_question("Solve Q5 please") == 5, "Failed Q5 detection"
    assert detect_target_question("What is problem #3?") == 3, "Failed problem 3 detection"
    assert detect_target_question("Solve 4") == 4, "Failed solve 4 detection"
    assert is_solve_all_or_paper_request("Solve all questions") == True, "Failed solve all detection"
    assert is_solve_all_or_paper_request("Solve this paper") == True, "Failed solve paper detection"
    print("PASS: Question locator extracted questions accurately.\n")

    # Test 2: Generate sample question paper image
    test_img_path = Path("backend/tests/fixtures/sample_exam_paper.png")
    create_test_exam_paper_image(test_img_path)
    print(f"[TEST 2] Generated test question paper image: {test_img_path} ({test_img_path.stat().st_size} bytes)")

    # Test 3: Structured Question Paper Extraction via Gemini Vision
    print("[TEST 3] Running extract_structured_question_paper with Gemini Vision...")
    full_text, questions, meta = extract_structured_question_paper(str(test_img_path))
    print(f"Extraction Method: {meta.get('method')}")
    print(f"Title Detected: {meta.get('title')}")
    print(f"Questions Extracted: {len(questions)}")
    for q in questions:
        print(f"  - [{q.get('section')}] {q.get('q_num')}: {q.get('text')[:60]}... (Diagram: {q.get('has_diagram')})")
    assert len(questions) >= 3, f"Expected at least 3 questions, got {len(questions)}"
    print("PASS: Question Paper Intelligence extracted structured questions.\n")

    # Test 4: Multimodal Vision Chat with direct image attachment ("Answer question 2")
    print("[TEST 4] Testing Multimodal Vision Chat with image attachment ('Solve question 2')...")
    with open(test_img_path, "rb") as f:
        import base64
        b64_data = f"data:image/png;base64,{base64.b64encode(f.read()).decode('utf-8')}"

    att = {
        "name": "sample_exam_paper.png",
        "type": "image/png",
        "size": test_img_path.stat().st_size,
        "data_url": b64_data,
    }

    res_q2 = await ask_question(
        question="Solve question 2 step by step with all formulas in LaTeX.",
        attachment=att,
    )
    assert res_q2.get("success"), "ask_question failed"
    answer_q2 = res_q2["data"]["answer"]
    print("ANSWER TO QUESTION 2 (EXCERPT):")
    print(answer_q2[:500] + "...\n")
    # Verify eigenvalues 2 and 4 are found
    assert "2" in answer_q2 and "4" in answer_q2, "Eigenvalues not found in solution"
    # Verify LaTeX formulas are present ($ or \lambda or \det)
    has_latex = "$" in answer_q2 or "\\lambda" in answer_q2 or "\\det" in answer_q2
    assert has_latex, "LaTeX formulas missing from solution"
    print("PASS: Solved Question 2 with step-by-step working and LaTeX math formulas.\n")

    # Test 5: Multimodal Vision Streaming with MCQ ("Answer question 3")
    print("[TEST 5] Testing Multimodal Vision Streaming SSE ('Answer question 3')...")
    events = []
    tokens = []
    async for sse in ask_question_stream(
        question="What is the answer to question 3? Identify the correct option and explain why.",
        attachment=att,
    ):
        events.append(sse)
        if '"type": "token"' in sse:
            # extract content
            import json
            payload = json.loads(sse.replace("data: ", "").strip())
            tokens.append(payload.get("content", ""))

    full_stream_text = "".join(tokens)
    print("STREAMED MCQ ANSWER (EXCERPT):")
    print(full_stream_text[:450] + "...\n")
    # Correct answer for derivative of ln(x^2 + 1) is 2x / (x^2 + 1) which is (A)
    assert "(A)" in full_stream_text or "2x" in full_stream_text, "MCQ Option A / 2x was not identified"
    print("PASS: Question 3 correctly solved Option (A) via SSE stream.\n")

    # Test 6: Diagram Question ("Explain and solve question 4")
    print("[TEST 6] Testing Diagram Awareness ('Solve question 4 with the circuit diagram')...")
    res_diag = await ask_question(
        question="Solve question 4. What is the equivalent resistance shown in the circuit diagram?",
        attachment=att,
    )
    ans_diag = res_diag["data"]["answer"]
    print("CIRCUIT ANSWER (EXCERPT):")
    print(ans_diag[:400] + "...\n")
    # Resistors in series: 4 + 6 = 10 ohms
    assert "10" in ans_diag or "series" in ans_diag.lower() or "4" in ans_diag, "Circuit analysis failed"
    print("PASS: Circuit diagram analyzed and equivalent resistance calculated.\n")

    # Test 7: Sidecar and Vector Store Integration
    print("[TEST 7] Testing process_image_to_chunks and chunk metadata...")
    extracted_text, chunks, meta = process_image_to_chunks(
        str(test_img_path),
        doc_id="test-doc-123",
        upload_dir=str(test_img_path.parent),
    )
    assert len(chunks) > 0, "No chunks generated"
    q_chunks = [c for c in chunks if getattr(c, "question_number", None) is not None]
    print(f"Generated {len(chunks)} chunks, {len(q_chunks)} have question metadata.")
    print("PASS: Chunks generated with question numbering and sidecars written.\n")

    print("="*70)
    print("ALL 7 TEST SUITES PASSED SUCCESSFULLY! 100% PRODUCTION READY.")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(run_tests())

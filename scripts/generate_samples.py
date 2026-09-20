"""Sample generator script for confidential refinery inspection, SOP, and P&ID drawings.

Generates realistic industrial sample files in data/samples/:
1. refinery_sop_402.txt: Standard Operating Procedure for PSV and piping integrity.
2. pid_drawing_sample.png: High-resolution technical Piping & Instrumentation Diagram.
3. inspection_report_sample.pdf: Standard-compliant PDF of ultrasonic inspection findings.
"""

from __future__ import annotations

import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent.parent
SAMPLES_DIR = BASE_DIR / "data" / "samples"


def generate_refinery_sop(output_path: Path) -> Path:
    """Generate authentic refinery SOP 402 text document."""
    content = """================================================================================
BHARAT REFINERIES & PETROCHEMICALS CORPORATION (A GOVT. OF INDIA ENTERPRISE)
CENTRAL TECHNICAL DIRECTORATE — SAFETY & PIPING INTEGRITY DIVISION
DOCUMENT NO: SOP-REF-402-REV4                               CLASSIFICATION: CONFIDENTIAL
================================================================================

STANDARD OPERATING PROCEDURE:
MONITORING, CORROSION ASSESSMENT, AND APPROVAL HIERARCHY FOR
HIGH-PRESSURE SAFETY RELIEF VALVES (PSVs) AND RECTIFICATION PROTOCOLS

--------------------------------------------------------------------------------
1. PURPOSE AND APPLICABILITY
--------------------------------------------------------------------------------
1.1 This Standard Operating Procedure defines the mandatory engineering inspection,
    ultrasonic thickness verification, corrosion rate monitoring, and administrative
    approval hierarchy for high-pressure safety relief valves (PSVs) and associated
    overhead hydrocarbon lines operating within Central Refinery Units.
1.2 Applicable to Atmospheric and Vacuum Distillation Units (AVDU), Fluidized Catalytic
    Cracking Units (FCCU), and Continuous Catalytic Reforming (CCR) blocks.
1.3 In accordance with Air-Gap Sovereign Compliance Directive 2026/SEC-04, no inspection
    telemetry, ultrasonic gauging data, or process flow diagrams shall be transmitted
    outside refinery premises or uploaded to public cloud infrastructure.

--------------------------------------------------------------------------------
2. ENGINEERING CODES & STATUTORY STANDARDS
--------------------------------------------------------------------------------
All evaluations and calculations must strictly adhere to:
- ASME Boiler and Pressure Vessel Code (BPVC), Section VIII, Division 1
- ASME B31.3: Process Piping Design and Allowable Stress Criteria
- API 520: Sizing, Selection, and Installation of Pressure-Relieving Devices
- API 526: Flanged Steel Pressure-Relief Valves
- API 570: Piping Inspection Code: In-service Inspection, Rating, Repair
- OISD-STD-132: Safety Relief and Depressurizing Systems (Oil Industry Safety Directorate)

--------------------------------------------------------------------------------
3. HIGH-PRESSURE SAFETY RELIEF VALVE (PSV) SCHEDULE
--------------------------------------------------------------------------------
The following critical safety devices are monitored under this protocol:

+----------+-----------------------+------------+----------------+-------------+
| Valve ID | Associated Equipment  | Line Tag   | Set Press(psi) | Orifice Des |
+----------+-----------------------+------------+----------------+-------------+
| PSV-401  | Pre-Flash Column V-10 | 08-CR-401  | 220.0 psig     | 4L6 (API)   |
| PSV-402  | Column C-101 Overhead | 10-HC-402  | 258.0 psig     | 6Q8 (API)   |
| PSV-403  | Reboiler E-102 Inlet  | 06-RB-403  | 312.0 psig     | 3K4 (API)   |
| PSV-404  | Accumulator Boot V-104| 04-AC-404  | 185.0 psig     | 2J3 (API)   |
+----------+-----------------------+------------+----------------+-------------+

--------------------------------------------------------------------------------
4. PROCESS PIPING WALL THICKNESS & CORROSION THRESHOLDS
--------------------------------------------------------------------------------
For Carbon Steel Line 10-HC-402 (ASTM A106 Grade B, NPS 10, Design Class 300):
- Nominal As-Built Wall Thickness:        9.53 mm (0.375 in / Schedule 40)
- Specified Corrosion Allowance (CA):     2.00 mm
- Calculated Minimum Design Thickness:    7.20 mm (t_min under ASME B31.3 at 258 psig)
- Mandatory Retirement Thickness (t_ret):  6.80 mm

Corrosion Rate Classifications:
- Normal Corrosion Rate:                  < 0.15 mm/year (Standard inspection cycle: 24 mos)
- Accelerated Corrosion:                  0.15 mm - 0.35 mm/year (Cycle reduced to 12 mos)
- Severe / Critical Thinning:             > 0.35 mm/year (Mandatory intervention within 30 days)

--------------------------------------------------------------------------------
5. ASME B31.3 MINIMUM THICKNESS FORMULA
--------------------------------------------------------------------------------
The minimum required pipe wall thickness (t_m) to resist internal design pressure
shall be calculated as:
                     P * D
    t_m = ----------------------------- + c
           2 * (S * E * W + P * Y)

Where:
    P = Internal design pressure (psig)
    D = Outside diameter of pipe (inches)
    S = Basic allowable stress of material at design temperature (psi)
    E = Longitudinal weld quality factor (1.00 for seamless)
    W = Weld joint strength reduction factor (1.00 for normal temperatures)
    Y = Material coefficient (0.40 for ferritic steels under 900 deg F)
    c = Sum of mechanical allowances + corrosion allowance (inches)

--------------------------------------------------------------------------------
6. MANDATORY RECTIFICATION & ACTION PROTOCOLS
--------------------------------------------------------------------------------
6.1 If measured ultrasonic wall thickness (t_actual) satisfies:
    t_actual >= 7.50 mm:
    -> Continue normal operation; log NDT report in local sovereign database.
6.2 If 7.20 mm <= t_actual < 7.50 mm:
    -> Issue Alert Level 2; mandate repeat ultrasonic gauging within 90 days.
    -> Verify that operating set pressure on PSV-402 is properly calibrated.
6.3 If t_actual < 7.20 mm (Deficient Wall Thickness):
    -> Issue Emergency Action Notice Level 1 immediately.
    -> Mandatory rectification within 30 days:
       Option A: Full spool piece replacement during planned unit decoking.
       Option B: ASME Section IX qualified structural weld overlay (pre-approved clamp).
       Option C: Immediate pressure derating certified by Technical Directorate.

--------------------------------------------------------------------------------
7. ADMINISTRATIVE APPROVAL HIERARCHY
--------------------------------------------------------------------------------
Official Approval Notes generated for inspection findings must be processed through
the following administrative sequence:

1. Field Inspection Officer (NDT Level II / III):
   - Conducts ultrasonic testing, visual examination, and drafts initial observations.
2. Executive Engineer (Inspection & Maintenance):
   - Verifies ASME B31.3 code calculations and checks SOP-REF-402 compliance.
3. Chief General Manager / Executive Director (Refinery Operations):
   - Final statutory approval authority for derating, repair authorizations, or
     procurement of emergency replacement spools.

================================================================================
END OF STANDARD OPERATING PROCEDURE — SOP-REF-402-REV4
================================================================================
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    return output_path


def generate_pid_drawing(output_path: Path) -> Path:
    """Generate high-resolution industrial Piping & Instrumentation Diagram image."""
    width, height = 1600, 1000
    # Technical dark blueprint / CAD slate background
    img = Image.new("RGB", (width, height), color=(248, 250, 252))
    draw = ImageDraw.Draw(img)

    # Color palette
    color_border = (30, 41, 59)       # Slate 800
    color_pipe = (15, 23, 42)         # Heavy dark pipe
    color_instrument = (37, 99, 235)  # Blue 600
    color_relief = (220, 38, 38)      # Red 600
    color_equipment = (51, 65, 85)    # Slate 700
    color_text = (15, 23, 42)         # Slate 900
    color_grid = (226, 232, 240)      # Grid line

    # 1. Subtle CAD Grid
    for x in range(50, width - 50, 50):
        draw.line([(x, 50), (x, height - 50)], fill=color_grid, width=1)
    for y in range(50, height - 50, 50):
        draw.line([(50, y), (width - 50, y)], fill=color_grid, width=1)

    # 2. Outer Border & Title Block
    draw.rectangle([(40, 40), (width - 40, height - 40)], outline=color_border, width=3)
    draw.rectangle([(width - 520, height - 160), (width - 40, height - 40)], outline=color_border, width=2)
    draw.line([(width - 520, height - 120), (width - 40, height - 120)], fill=color_border, width=1)
    draw.line([(width - 520, height - 80), (width - 40, height - 80)], fill=color_border, width=1)
    draw.line([(width - 260, height - 120), (width - 260, height - 40)], fill=color_border, width=1)

    draw.text((width - 510, height - 150), "BHARAT REFINERIES — CENTRAL ENGG DIV", fill=color_text)
    draw.text((width - 510, height - 110), "P&ID: ATMOSPHERIC DISTILLATION C-101", fill=color_text)
    draw.text((width - 250, height - 110), "DWG NO: 26117-PID-004-REV2", fill=color_text)
    draw.text((width - 510, height - 70), "AIR-GAP SOVEREIGN WORKBENCH DEMO", fill=(185, 28, 28))
    draw.text((width - 250, height - 70), "STATUS: APPROVED FOR OPERATION", fill=(21, 128, 61))

    # Top Header
    draw.text((60, 55), "SOVEREIGN ON-PREMISE AGENTIC AI WORKBENCH — TEST P&ID SCHEMATIC (PROBLEM STATEMENT ID: 26117)", fill=color_text)

    # 3. Main Equipment Vessels
    # Distillation Column C-101 (Center-Left)
    col_x1, col_y1, col_x2, col_y2 = 350, 180, 520, 720
    draw.rectangle([(col_x1, col_y1), (col_x2, col_y2)], outline=color_equipment, width=4, fill=(241, 245, 249))
    # Tray internal lines
    for ty in range(230, 680, 45):
        draw.line([(col_x1 + 10, ty), (col_x2 - 10, ty)], fill=(148, 163, 184), width=1)
    draw.text((col_x1 + 25, col_y1 + 20), "FRACTIONATOR", fill=color_equipment)
    draw.text((col_x1 + 55, col_y1 + 45), "C-101", fill=color_equipment)

    # Overhead Accumulator V-104 (Top-Right)
    acc_x1, acc_y1, acc_x2, acc_y2 = 880, 200, 1080, 320
    draw.rounded_rectangle([(acc_x1, acc_y1), (acc_x2, acc_y2)], radius=20, outline=color_equipment, width=3, fill=(241, 245, 249))
    draw.text((acc_x1 + 30, acc_y1 + 45), "OVERHEAD ACCUMULATOR", fill=color_equipment)
    draw.text((acc_x1 + 80, acc_y1 + 70), "V-104", fill=color_equipment)

    # Bottoms Reboiler E-102 (Bottom-Right)
    reb_x1, reb_y1, reb_x2, reb_y2 = 680, 620, 840, 740
    draw.rounded_rectangle([(reb_x1, reb_y1), (reb_x2, reb_y2)], radius=15, outline=color_equipment, width=3, fill=(241, 245, 249))
    draw.text((reb_x1 + 20, reb_y1 + 40), "REBOILER E-102", fill=color_equipment)

    # Feed Furnace F-101 (Far-Left)
    fur_x1, fur_y1, fur_x2, fur_y2 = 120, 420, 230, 620
    draw.rectangle([(fur_x1, fur_y1), (fur_x2, fur_y2)], outline=color_equipment, width=3, fill=(241, 245, 249))
    draw.text((fur_x1 + 15, fur_y1 + 85), "FURNACE F-101", fill=color_equipment)

    # 4. Piping Process Lines (Thick Dark Lines)
    # Feed line from Furnace to Column
    draw.line([(230, 520), (350, 520)], fill=color_pipe, width=4)
    draw.text((245, 500), "8\"-CR-101-CS150", fill=color_text)

    # Overhead Vapor Line from C-101 top to Accumulator V-104
    # Column top nozzle: (435, 180) -> up to 120 -> across to 980 -> down to V-104 (980, 200)
    draw.line([(435, 180), (435, 120), (980, 120), (980, 200)], fill=color_pipe, width=4)
    draw.text((580, 100), "10\"-HC-402-CS300 (CRITICAL VAPOR OVERHEAD)", fill=color_relief)

    # Relief Line branch up to PSV-402
    draw.line([(720, 120), (720, 75)], fill=color_relief, width=3)
    # PSV-402 Symbol (Angled relief valve)
    draw.polygon([(705, 75), (735, 75), (720, 55)], outline=color_relief, fill=(254, 226, 226))
    draw.line([(720, 55), (760, 55)], fill=color_relief, width=2)
    # PSV-402 Instrument Balloon
    draw.ellipse([(760, 40), (830, 80)], outline=color_relief, width=2, fill=(255, 255, 255))
    draw.text((770, 50), "PSV-402", fill=color_relief)
    draw.text((762, 85), "Set: 258 psig", fill=color_relief)

    # Column Bottoms line to Reboiler
    draw.line([(435, 720), (435, 760), (760, 760), (760, 740)], fill=color_pipe, width=4)
    draw.text((510, 740), "6\"-BT-105-CS150", fill=color_text)

    # Reboiler vapor return line to column
    draw.line([(680, 680), (520, 680)], fill=color_pipe, width=3)
    draw.text((545, 660), "6\"-RV-106", fill=color_text)

    # 5. Instruments & Valves
    # FT-102 on Feed Line
    draw.line([(290, 520), (290, 460)], fill=color_instrument, width=2)
    draw.ellipse([(265, 420), (315, 460)], outline=color_instrument, width=2, fill=(255, 255, 255))
    draw.text((272, 432), "FT-102", fill=color_instrument)

    # PCV-101 on Overhead line before accumulator
    pcv_x, pcv_y = 860, 120
    draw.polygon([(pcv_x - 15, pcv_y - 12), (pcv_x + 15, pcv_y + 12), (pcv_x + 15, pcv_y - 12), (pcv_x - 15, pcv_y + 12)], outline=color_instrument, fill=(219, 234, 254))
    draw.line([(pcv_x, pcv_y - 12), (pcv_x, pcv_y - 35)], fill=color_instrument, width=2)
    draw.ellipse([(pcv_x - 25, pcv_y - 75), (pcv_x + 25, pcv_y - 35)], outline=color_instrument, width=2, fill=(255, 255, 255))
    draw.text((pcv_x - 20, pcv_y - 62), "PCV-101", fill=color_instrument)

    # TI-103 on Column Mid-section
    draw.line([(520, 400), (570, 400)], fill=color_instrument, width=2)
    draw.ellipse([(570, 380), (620, 420)], outline=color_instrument, width=2, fill=(255, 255, 255))
    draw.text((577, 392), "TI-103", fill=color_instrument)

    # LT-104 on Accumulator V-104
    draw.line([(1080, 260), (1130, 260)], fill=color_instrument, width=2)
    draw.ellipse([(1130, 240), (1180, 280)], outline=color_instrument, width=2, fill=(255, 255, 255))
    draw.text((1137, 252), "LT-104", fill=color_instrument)

    # Legend Block
    draw.rectangle([(60, 780), (380, 930)], outline=color_border, width=1, fill=(255, 255, 255))
    draw.text((70, 790), "INSTRUMENTATION LEGEND", fill=color_text)
    draw.text((70, 815), "• PSV: Pressure Safety Relief Valve", fill=color_relief)
    draw.text((70, 840), "• PCV: Pressure Control Valve", fill=color_instrument)
    draw.text((70, 865), "• FT:  Flow Transmitter (Orifice)", fill=color_instrument)
    draw.text((70, 890), "• TI:  Temperature Indicator (RTD)", fill=color_instrument)
    draw.text((70, 910), "• LT:  Level Transmitter (Radar)", fill=color_instrument)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")
    return output_path


def generate_inspection_pdf(output_path: Path) -> Path:
    """Generate standard-compliant, portable PDF 1.4 inspection report without external libraries."""
    lines = [
        "BHARAT REFINERIES & PETROCHEMICALS CORPORATION",
        "CENTRAL INSPECTION & NON-DESTRUCTIVE TESTING DIVISION",
        "============================================================",
        "ANNUAL COMPREHENSIVE ULTRASONIC INSPECTION REPORT: 2026",
        "Document Ref: BRPC/INSP/AVDU-02/UTG-402     Date: 15-JAN-2026",
        "Refinery Unit: Atmospheric Vacuum Distillation Unit (AVDU-02)",
        "Equipment: Fractionator Column C-101 Overhead Vapor Circuit",
        "Piping Line Identifier: 10-HC-402-CS300 (NPS 10 Carbon Steel)",
        "Design Standard: ASME B31.3 / API 570      Class: 300#",
        "Design Pressure: 258 psig (18.2 kg/cm2g)   Design Temp: 320 F",
        "------------------------------------------------------------",
        "EXECUTIVE SUMMARY & ULTRASONIC GAUGING FINDINGS:",
        "1. Nominal As-Built Wall Thickness: 9.53 mm (0.375 in, Sch 40)",
        "2. Specified Minimum Corrosion Allowance (CA): 2.00 mm",
        "3. Calculated ASME B31.3 Minimum Wall Thickness (t_min): 7.20 mm",
        "4. Retirement Wall Thickness Limit (t_ret): 6.80 mm",
        "",
        "ULTRASONIC THICKNESS GAUGING (UTG) RESULTS AT CRITICAL TMLs:",
        "+----------+-------------------------+-------------+---------+",
        "| TML No.  | Inspection Location     | Thick (mm)  | Status  |",
        "+----------+-------------------------+-------------+---------+",
        "| TML-01   | Column C-101 Top Nozzle | 8.92 mm     | NORMAL  |",
        "| TML-02   | Overhead Elbow E-01     | 8.10 mm     | NORMAL  |",
        "| TML-03   | Safety Valve PSV-402 In | 7.95 mm     | MONITOR |",
        "| TML-04   | Elbow E-04 Weld W-12    | 7.15 mm     | DEFICIENT",
        "| TML-05   | Accumulator V-104 Inlet | 8.45 mm     | NORMAL  |",
        "+----------+-------------------------+-------------+---------+",
        "",
        "CRITICAL DEFECT ANALYSIS (TML-04 / ELBOW E-04):",
        "- Measured Wall Thickness: 7.15 mm (BELOW MINIMUM DESIGN 7.20 mm)",
        "- Historical Thickness (2024 Inspection): 8.05 mm",
        "- Metal Loss over 24 Months: 0.90 mm (Corrosion Rate: 0.45 mm/yr)",
        "- Accelerated localized pitting corrosion observed near weld seam W-12",
        "  caused by ammonium chloride salt deposition and wet H2S condensation.",
        "",
        "MANDATORY RECOMMENDATIONS UNDER REFINERY SOP-REF-402:",
        "1. Issue Immediate Alert Notice Level 1 for Line 10-HC-402.",
        "2. Prepare formal PSU Approval Note for Chief General Manager (CGM).",
        "3. Perform ASME Sec IX qualified structural weld overlay within 30 days.",
        "4. Recalibrate and verify set pressure on Safety Relief Valve PSV-402.",
        "5. Conduct follow-up ultrasonic testing in 90 days to verify integrity.",
        "------------------------------------------------------------",
        "Inspected By: Er. R. K. Sharma (NDT Level III - UT/VT/MT)",
        "Verified By:  Er. S. Sengupta (Chief Inspection Engineer)",
        "Classification: STRICTLY CONFIDENTIAL - AIR-GAP ON-PREMISE ONLY",
        "============================================================",
    ]

    # Build PDF content stream
    text_stream = ["BT", "/F1 10 Tf", "36 750 Td", "13 TL"]
    for i, line in enumerate(lines):
        # Escape parenthesis and backslashes
        safe_line = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if i == 0:
            text_stream.append(f"({safe_line}) Tj")
        else:
            text_stream.append(f"T* ({safe_line}) Tj")
    text_stream.append("ET")
    content_bytes = "\n".join(text_stream).encode("latin-1")

    # Generate PDF objects
    objs = []
    objs.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    objs.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    objs.append(
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n"
    )
    objs.append(b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>\nendobj\n")
    objs.append(
        f"5 0 obj\n<< /Length {len(content_bytes)} >>\nstream\n".encode("latin-1")
        + content_bytes
        + b"\nendstream\nendobj\n"
    )

    pdf_parts = [b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"]
    xref_offsets = [0]

    offset = len(pdf_parts[0])
    for obj in objs:
        xref_offsets.append(offset)
        pdf_parts.append(obj)
        offset += len(obj)

    xref_start = offset
    xref = [f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode("latin-1")]
    for off in xref_offsets[1:]:
        xref.append(f"{off:010d} 00000 n \n".encode("latin-1"))

    trailer = (
        f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_start}\n%%EOF\n"
    ).encode("latin-1")

    pdf_data = b"".join(pdf_parts) + b"".join(xref) + trailer

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(pdf_data)
    return output_path


def generate_all_samples():
    """Generate all 3 sample files."""
    print("Generating industrial demo samples...")
    sop_path = SAMPLES_DIR / "refinery_sop_402.txt"
    pid_path = SAMPLES_DIR / "pid_drawing_sample.png"
    pdf_path = SAMPLES_DIR / "inspection_report_sample.pdf"

    generate_refinery_sop(sop_path)
    print(f"  [OK] Created SOP: {sop_path} ({sop_path.stat().st_size} bytes)")

    generate_pid_drawing(pid_path)
    print(f"  [OK] Created P&ID Diagram: {pid_path} ({pid_path.stat().st_size} bytes)")

    generate_inspection_pdf(pdf_path)
    print(f"  [OK] Created PDF Report: {pdf_path} ({pdf_path.stat().st_size} bytes)")

    print("All sample files generated successfully.")


if __name__ == "__main__":
    generate_all_samples()

# ======================
# NutriScan – Professional UI Version
# Gemini 2.5 Flash • Realistic Design Update
# Features: Personalized Nutrition Tracking, User Profiles, Weekly Insights
# ======================

import os
import json
import uuid
import base64
from io import BytesIO
from datetime import datetime, timedelta

# Matplotlib for Charts
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from PIL import Image
from flask import Flask, request, render_template, url_for, redirect, session, send_file

# ReportLab imports for PDF
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image as ReportLabImage
)
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# Gemini SDK (optional)
try:
    from google import genai
    GEMINI_AVAILABLE = True
except:
    GEMINI_AVAILABLE = False

# ---------------- CONFIG ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
tmp_dir = os.path.join(BASE_DIR, "tmp")
os.makedirs(tmp_dir, exist_ok=True)

ALLOWED = {".jpg", ".jpeg", ".png", ".webp"}

app = Flask(__name__, template_folder="templates")
app.secret_key = "nutriscan-key-2025"

# Fallback image if user image is missing
FALLBACK_IMAGE = "/mnt/data/d3399e67-75a3-42db-9b41-317da1e897a0.png"

# ------------ Load Gemini Key -------------
def load_key():
    if "GEMINI_API_KEY" in os.environ:
        return os.environ["GEMINI_API_KEY"]
    fp = os.path.join(BASE_DIR, "gemini_key.txt")
    if os.path.exists(fp):
        return open(fp).read().strip()
    return None

GEMINI_KEY = load_key()
GENAI = None

if GEMINI_AVAILABLE and GEMINI_KEY:
    try:
        GENAI = genai.Client(api_key=GEMINI_KEY)
        print("🔥 Gemini Connected")
    except:
        GENAI = None
        print("❌ Gemini init failed")

# ---------------- Helpers ----------------
def safe_float(x):
    try:
        return float(str(x).replace(",", "").strip())
    except:
        return 0.0

def read_bytes(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except:
        return None

# ----------- User Profile Management -----------
def get_user_profile():
    """Get or create user profile"""
    profile_file = os.path.join(BASE_DIR, "user_profile.json")
    if os.path.exists(profile_file):
        try:
            return json.load(open(profile_file))
        except:
            pass
    
    # Default profile
    default_profile = {
        "weight": 70,  # kg
        "height": 170, # cm
        "age": 30,
        "gender": "male",
        "activity_level": "moderate",
        "goal": "maintain",
        "created_at": datetime.now().isoformat()
    }
    save_user_profile(default_profile)
    return default_profile

def save_user_profile(profile):
    """Save user profile"""
    profile_file = os.path.join(BASE_DIR, "user_profile.json")
    with open(profile_file, "w") as f:
        json.dump(profile, f, indent=4)

def calculate_daily_needs(profile):
    """Calculate daily calorie and nutrient needs based on profile"""
    weight = profile.get("weight", 70)
    height = profile.get("height", 170)
    age = profile.get("age", 30)
    gender = profile.get("gender", "male")
    activity_level = profile.get("activity_level", "moderate")
    goal = profile.get("goal", "maintain")
    
    # BMR calculation (Mifflin-St Jeor Equation)
    if gender == "male":
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161
    
    # Activity multiplier
    activity_multipliers = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
        "very_active": 1.9
    }
    
    tdee = bmr * activity_multipliers.get(activity_level, 1.55)
    
    # Goal adjustment
    goal_adjustments = {
        "lose": 0.85,
        "maintain": 1.0,
        "gain": 1.15
    }
    
    daily_calories = tdee * goal_adjustments.get(goal, 1.0)
    
    # Macronutrient distribution (in grams)
    protein_g = (daily_calories * 0.3) / 4  # 30% from protein
    fat_g = (daily_calories * 0.25) / 9     # 25% from fat
    carbs_g = (daily_calories * 0.45) / 4   # 45% from carbs
    
    return {
        "daily_calories": round(daily_calories),
        "protein": round(protein_g),
        "fat": round(fat_g),
        "carbs": round(carbs_g),
        "sugar_limit": round(daily_calories * 0.1 / 4),  # Max 10% from sugar
        "fiber_target": 25  # grams
    }


def time_ago(ts):
    if not ts:
        return ""

    try:
        dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
    except:
        return ""  # if parsing fails

    now = datetime.now() 
    diff = now - dt

    seconds = diff.total_seconds()
    minutes = seconds // 60
    hours = seconds // 3600
    days = seconds // 86400

    if seconds < 60:
        return "Just now"
    elif minutes < 60:
        return f"{int(minutes)} mins ago"
    elif hours < 24:
        return f"{int(hours)} hours ago"
    else:
        return f"{int(days)} days ago"

def get_weekly_nutrition():
    """Get nutrition data for the last 7 days"""
    history_file = os.path.join(BASE_DIR, "history.json")
    if not os.path.exists(history_file):
        return []
    
    try:
        history = json.load(open(history_file))
    except:
        return []
    
    # Filter last 7 days
    week_ago = datetime.now() - timedelta(days=7)
    weekly_data = []
    
    for entry in history:
        try:
            entry_date = datetime.strptime(entry["timestamp"], "%Y-%m-%d %H:%M:%S")
            if entry_date >= week_ago:
                weekly_data.append(entry)
        except:
            continue
    
    return weekly_data

def generate_personalized_recommendations(weekly_data, daily_needs):
    """Generate personalized recommendations based on weekly intake"""
    if not weekly_data:
        return ["Start tracking your food to get personalized recommendations!"]
    
    # Calculate weekly averages
    total_days = min(len(weekly_data), 7)
    weekly_totals = {
        "calories": 0,
        "protein": 0,
        "fat": 0,
        "carbs": 0,
        "sugar": 0
    }
    
    for entry in weekly_data[:7]:  # Last 7 entries
        weekly_totals["calories"] += entry.get("calories", 0)
        nutrition = entry.get("nutrition", [])
        for nutrient in nutrition:
            if nutrient["name"] == "protein":
                weekly_totals["protein"] += nutrient["value"]
            elif nutrient["name"] == "fat":
                weekly_totals["fat"] += nutrient["value"]
            elif nutrient["name"] == "carbohydrates":
                weekly_totals["carbs"] += nutrient["value"]
            # Note: Sugar tracking would need to be added to Gemini analysis
    
    # Calculate daily averages
    daily_avg = {k: v / total_days for k, v in weekly_totals.items()}
    
    recommendations = []
    
    # Calorie analysis
    calorie_ratio = daily_avg["calories"] / daily_needs["daily_calories"]
    if calorie_ratio > 1.2:
        recommendations.append("You're consuming 20% more calories than needed. Consider smaller portions.")
    elif calorie_ratio < 0.8:
        recommendations.append("You're under-eating. Try to increase your calorie intake with healthy foods.")
    else:
        recommendations.append("Your calorie intake is well balanced. Keep it up!")
    
    # Protein analysis
    protein_ratio = daily_avg["protein"] / daily_needs["protein"]
    if protein_ratio < 0.8:
        recommendations.append(f"Increase protein intake. Aim for {daily_needs['protein']}g daily. Try adding lean meats, eggs, or legumes.")
    elif protein_ratio > 1.3:
        recommendations.append("Your protein intake is quite high. Make sure to balance with other nutrients.")
    
    # Fat analysis
    fat_ratio = daily_avg["fat"] / daily_needs["fat"]
    if fat_ratio > 1.2:
        recommendations.append("Consider reducing fat intake. Choose baked over fried foods.")
    elif fat_ratio < 0.7:
        recommendations.append("Your fat intake is low. Include healthy fats like nuts, avocado, or olive oil.")
    
    # Carbohydrate analysis
    carbs_ratio = daily_avg["carbs"] / daily_needs["carbs"]
    if carbs_ratio > 1.3:
        recommendations.append("High carb intake detected. Balance with more protein and vegetables.")
    
    # General health tips
    if len(weekly_data) < 3:
        recommendations.append("Track more meals to get better insights into your eating patterns.")
    
    return recommendations[:5]  # Return top 5 recommendations

# ----------- Gemini Analysis --------------
def analyze_with_gemini(image_bytes):
    if GENAI is None:
        raise RuntimeError("Gemini not available")

    prompt = """
    Analyze this food image.
    Return JSON ONLY:
    {
      "main_food": "string",
      "top": [{"label":"food","score":0.95}],
      "nutrition_per100g": {"protein":10,"calcium":5,"fat":9,"carbohydrates":20,"vitamins":2},
      "calories_per100g": 250,
      "hygiene": {"score":75,"reasons":["clean surface","fresh ingredients"]}
    }
    """

    try:
        pil = Image.open(BytesIO(image_bytes)).convert("RGB")
    except:
        raise RuntimeError("Invalid Image")

    resp = GENAI.models.generate_content(
        model="gemini-2.5-flash",
        contents=[prompt, pil]
    )

    text = ""
    for part in resp.candidates[0].content.parts:
        if hasattr(part, "text"):
            text += part.text
    text = text.strip()

    try:
        parsed = json.loads(text)
    except:
        s = text.find("{")
        e = text.rfind("}")
        parsed = json.loads(text[s:e+1])

    preds = []
    for t in parsed.get("top", []):
        lbl = t.get("label", "").lower()
        sc = safe_float(t.get("score"))
        if sc <= 1: sc *= 100
        preds.append({"label": lbl, "score": round(sc, 1)})

    if not preds:
        preds = [{"label": parsed.get("main_food", "food"), "score": 85}]

    return {
        "main_food": parsed.get("main_food", "unknown"),
        "top": preds,
        "nutrition_per100g": parsed.get("nutrition_per100g", {}),
        "calories_per100g": parsed.get("calories_per100g", 0),
        "hygiene_score": int(parsed.get("hygiene", {}).get("score", 60)),
        "hygiene_reasons": parsed.get("hygiene", {}).get("reasons", [])
    }

# ----------- Nutrition Math ----------
def compute_nutrition(nut_map, qty, calories100):
    factor = qty / 100.0
    keys = ["protein", "calcium", "fat", "carbohydrates", "vitamins"]
    final = []
    for k in keys:
        v = safe_float(nut_map.get(k, 0))
        final.append({"name": k, "value": round(v * factor, 2)})

    if calories100:
        calories = round(safe_float(calories100) * factor, 2)
    else:
        p = final[0]["value"]
        c = final[3]["value"]
        f = final[2]["value"]
        calories = round(p*4 + c*4 + f*9, 2)

    return final, calories

# ============ CHART GENERATION FUNCTIONS ============
def generate_nutrition_pie_chart(weekly_data):
    """Generate pie chart of weekly nutrient distribution and return as base64"""
    if not weekly_data:
        return generate_placeholder_chart()
    
    # Calculate total nutrients
    totals = {"Protein": 0, "Fat": 0, "Carbs": 0, "Other": 0}
    
    for entry in weekly_data:
        nutrition = entry.get("nutrition", [])
        for nutrient in nutrition:
            name = nutrient["name"].lower()
            value = nutrient["value"]
            
            if name == "protein":
                totals["Protein"] += value
            elif name == "fat":
                totals["Fat"] += value
            elif name in ["carbohydrates", "carbs"]:
                totals["Carbs"] += value
            else:
                totals["Other"] += value
    
    # Filter out zero values
    labels = []
    values = []
    for label, value in totals.items():
        if value > 0:
            labels.append(label)
            values.append(value)
    
    if not values or sum(values) == 0:
        return generate_placeholder_chart()
    
    try:
        plt.figure(figsize=(8, 6))
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4']
        
        # Create pie chart with better styling
        wedges, texts, autotexts = plt.pie(
            values, 
            labels=labels, 
            autopct='%1.1f%%',
            startangle=90,
            colors=colors[:len(values)],
            textprops={'fontsize': 12}
        )
        
        # Improve text styling
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
            autotext.set_fontsize(10)
        
        plt.title('Weekly Nutrient Distribution', fontsize=14, fontweight='bold', pad=20)
        plt.axis('equal')  # Equal aspect ratio ensures pie is circular
        plt.tight_layout()
        
        # Save to bytes buffer instead of file
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight', facecolor='white')
        plt.close()
        
        # Convert to base64
        buffer.seek(0)
        image_png = buffer.getvalue()
        buffer.close()
        
        graphic = base64.b64encode(image_png).decode('utf-8')
        return f"data:image/png;base64,{graphic}"
        
    except Exception as e:
        print(f"Chart generation error: {e}")
        return generate_placeholder_chart()

def generate_placeholder_chart():
    """Generate a placeholder chart when no data is available"""
    try:
        plt.figure(figsize=(8, 6))
        
        # Create a simple placeholder chart
        labels = ['Protein', 'Carbs', 'Fat']
        values = [1, 1, 1]  # Equal parts
        
        plt.pie(values, labels=labels, autopct='%1.1f%%', startangle=90,
                colors=['#FF6B6B', '#4ECDC4', '#45B7D1'])
        plt.title('Scan Foods to See Your Nutrition Data', fontsize=14, fontweight='bold')
        plt.axis('equal')
        plt.tight_layout()
        
        # Save to bytes buffer
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight', facecolor='white')
        plt.close()
        
        # Convert to base64
        buffer.seek(0)
        image_png = buffer.getvalue()
        buffer.close()
        
        graphic = base64.b64encode(image_png).decode('utf-8')
        return f"data:image/png;base64,{graphic}"
        
    except Exception as e:
        print(f"Placeholder chart error: {e}")
        return None

# ==========================================
#   REALISTIC PDF GENERATION ENGINE
# ==========================================
def generate_pdf_report(item):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            leftMargin=0.5*inch, rightMargin=0.5*inch,
                            topMargin=0.6*inch, bottomMargin=0.6*inch)

    styles = getSampleStyleSheet()
    
    # --- Custom Design Palette ---
    COLOR_PRIMARY = colors.HexColor("#2C3E50")    # Dark Slate (Headings)
    COLOR_ACCENT  = colors.HexColor("#E67E22")    # Carrot Orange (Food Name)
    COLOR_BG_CARD = colors.HexColor("#F8F9FA")    # Light Grey (Card BG)
    COLOR_DIVIDER = colors.HexColor("#E0E0E0")    # Light divider line
    
    # --- Typography Styles ---
    # Main Header
    style_title = ParagraphStyle('MainTitle', parent=styles['Heading1'], fontSize=26, leading=32, 
                                 alignment=TA_CENTER, textColor=COLOR_PRIMARY, fontName="Helvetica-Bold")
    
    # Subtitles (e.g., "Nutrition Breakdown")
    style_section = ParagraphStyle('Section', parent=styles['Heading3'], fontSize=15, 
                                   textColor=COLOR_PRIMARY, spaceAfter=8, fontName="Helvetica-Bold")
    
    # Food Name (Large, Orange)
    style_food = ParagraphStyle('FoodName', parent=styles['Normal'], fontSize=20, leading=24,
                                textColor=COLOR_ACCENT, spaceAfter=12, fontName="Helvetica-Bold")
    
    # Labels (e.g., "Calories:")
    style_label = ParagraphStyle('Label', parent=styles['Normal'], fontSize=11, textColor=colors.gray)
    
    # Values (e.g., "280 kcal")
    style_value = ParagraphStyle('Value', parent=styles['Normal'], fontSize=12, textColor=colors.black, fontName="Helvetica-Bold")

    story = []

    # 1. Header Area
    story.append(Paragraph("NutriScan Report", style_title))
    story.append(Spacer(1, 20))
    story.append(Paragraph("_" * 65, ParagraphStyle('Line', parent=styles['Normal'], alignment=TA_CENTER, textColor=COLOR_DIVIDER)))
    story.append(Spacer(1, 25))

    # --- IMAGE HANDLING ---
    img_path = None
    img_ref = item.get('image', '')
    if img_ref:
        if img_ref.startswith("/"):
            candidate = os.path.join(BASE_DIR, img_ref.lstrip("/"))
        else:
            candidate = os.path.join(BASE_DIR, img_ref)
        if os.path.exists(candidate):
            img_path = candidate
    
    if not img_path and os.path.exists(FALLBACK_IMAGE):
        img_path = FALLBACK_IMAGE

    # --- CHART GENERATION (Matplotlib Donut) ---
    chart_filename = f"chart_{uuid.uuid4().hex}.png"
    chart_path = os.path.join(tmp_dir, chart_filename)
    
    whole = item.get("whole_nutrition", [])
    # Filter only significant values for the chart
    labels = []
    values = []
    for p in whole:
        val = float(p.get('value', 0))
        if val > 0.5: # Only show if > 0.5g
            labels.append(p['name'].capitalize())
            values.append(val)

    if not values:
        labels, values = ["N/A"], [1]

    # Professional Pastel Palette
    # Blue, Orange, Green, Red, Yellow (Muted)
    colors_pie = ['#4D96FF', '#FF6B6B', '#6BCB77', '#FFD93D', '#A2D2FF']

    try:
        plt.figure(figsize=(4, 4))
        # Donut Chart Logic
        wedges, texts, autotexts = plt.pie(
            values, 
            labels=labels, 
            autopct='%1.1f%%',   # Show percentages inside
            startangle=140, 
            colors=colors_pie,
            pctdistance=0.75,    # Move % towards edge
            textprops={'fontsize': 9} # Label font size
        )
        
        # Style the percentages to be white and bold
        plt.setp(autotexts, size=8, weight="bold", color="white")
        
        # Draw a white circle at center to make it a Donut
        centre_circle = plt.Circle((0,0),0.50,fc='white')
        fig = plt.gcf()
        fig.gca().add_artist(centre_circle)
        
        plt.tight_layout()
        plt.savefig(chart_path, dpi=100, transparent=True)
        plt.close()
    except:
        pass

    # ================= LEFT COLUMN (Image + Stats) =================
    left_flow = []
    
    # Food Image
    if img_path:
        # Constrain aspect ratio
        im = ReportLabImage(img_path, width=3.2*inch, height=2.4*inch)
        im.hAlign = 'LEFT'
        left_flow.append(im)
    else:
        left_flow.append(Paragraph("(No Image)", style_label))
    
    left_flow.append(Spacer(1, 15))
    
    # Food Title
    food_title = item.get('main_food', 'Unknown').title()
    left_flow.append(Paragraph("Image Name:", ParagraphStyle('SubLabel', parent=styles['Normal'], fontSize=10, textColor=colors.gray)))
    left_flow.append(Paragraph(food_title, style_food))
    
    # Stats List (Calories, Quantity, Protein)
    cal = item.get('calories', 0)
    qty = item.get('quantity', 0)
    prot = next((n['value'] for n in item.get('nutrition', []) if n['name']=='protein'), 0)
    
    stats_data = [
        [Paragraph("• Calories:", style_label), Paragraph(f"{cal} kcal", style_value)],
        [Paragraph("• Quantity:", style_label), Paragraph(f"{qty} g", style_value)],
        [Paragraph("• Protein:", style_label),  Paragraph(f"{prot} g", style_value)],
    ]
    stats_tbl = Table(stats_data, colWidths=[1.0*inch, 1.8*inch])
    stats_tbl.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    left_flow.append(stats_tbl)

    # ================= RIGHT COLUMN (Chart + Table) =================
    right_flow = []
    
    # Chart Image
    if os.path.exists(chart_path):
        cim = ReportLabImage(chart_path, width=3.0*inch, height=3.0*inch)
        right_flow.append(cim)
    
    right_flow.append(Spacer(1, 5))
    right_flow.append(Paragraph("Nutrition Breakdown", style_section))
    
    # Detailed Nutrition Table
    nut_data = []
    for n in item.get('nutrition', []):
        name = n['name'].capitalize()
        val = n['value']
        nut_data.append([
            Paragraph(name, style_label), 
            Paragraph(f"{val}g", style_value)
        ])
        
    nut_tbl = Table(nut_data, colWidths=[1.8*inch, 1.0*inch])
    nut_tbl.setStyle(TableStyle([
        ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor("#EEEEEE")),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    right_flow.append(nut_tbl)

    # ================= MAIN LAYOUT =================
    # 2 Columns with Vertical Divider
    main_data = [[left_flow, right_flow]]
    main_tbl = Table(main_data, colWidths=[3.7*inch, 3.7*inch])
    main_tbl.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (0,0), 5),
        ('RIGHTPADDING', (0,0), (0,0), 15),
        ('LEFTPADDING', (1,0), (1,0), 15),
        # Vertical Line Divider
        ('LINEAFTER', (0,0), (0,-1), 1, COLOR_DIVIDER),
    ]))
    story.append(main_tbl)
    
    story.append(Spacer(1, 30))

    # ================= HYGIENE CARD (Bottom) =================
    
    # "Card" Logic: A table with background color and rounded look
    
    notes = item.get('hygiene_reasons', [])
    note_content = []
    
    # Card Header
    note_content.append(Paragraph("Hygienic Notes", ParagraphStyle('HygTitle', parent=styles['Heading3'], fontSize=14, textColor=COLOR_PRIMARY, spaceAfter=8)))
    
    # Card Body
    if not notes:
        note_content.append(Paragraph("No specific hygiene comments.", styles['Normal']))
    else:
        for note in notes:
            note_content.append(Paragraph(f"• {note}", ParagraphStyle('NoteItem', parent=styles['Normal'], fontSize=11, leading=15, spaceAfter=4)))
            
    # Wrap content in a table cell
    card_data = [[note_content]]
    card_tbl = Table(card_data, colWidths=[7.2*inch])
    card_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), COLOR_BG_CARD),  # Light Grey/Beige Background
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#DDDDDD")), # Subtle Border
        ('LEFTPADDING', (0,0), (-1,-1), 15),
        ('RIGHTPADDING', (0,0), (-1,-1), 15),
        ('TOPPADDING', (0,0), (-1,-1), 15),
        ('BOTTOMPADDING', (0,0), (-1,-1), 15),
        ('ROUNDEDCORNERS', [10, 10, 10, 10]), # Requires newer reportlab, ignores if old
    ]))
    
    story.append(card_tbl)

    # Footer
    story.append(Spacer(1, 25))
    footer_text = f"Generated by NutriScan AI • {datetime.now().strftime('%d %B %Y')}"
    story.append(Paragraph(footer_text, ParagraphStyle('Footer', parent=styles['Normal'], fontSize=9, textColor=colors.gray, alignment=TA_CENTER)))

    doc.build(story)
    buffer.seek(0)
    
    # Cleanup
    if os.path.exists(chart_path):
        try: os.remove(chart_path)
        except: pass

    return buffer


# ================= ROUTES =================
@app.route("/")
def index():
    history_file = os.path.join(BASE_DIR, "history.json")
    profile_file = os.path.join(BASE_DIR, "user_profile.json")

    if not os.path.exists(history_file) or os.path.getsize(history_file) == 0:
        history = []
    else:
        try:
            history = json.load(open(history_file))
        except:
            history = []

    profile = get_user_profile()
    daily_needs = calculate_daily_needs(profile)

    total_analyses = len(history)

    weekly_data = get_weekly_nutrition()
    weekly_scans = len(weekly_data)

    total_calories = sum(entry.get("calories", 0) for entry in history)
    avg_calories = round(total_calories / max(total_analyses, 1))
    avg_hygiene = round(sum(entry.get("hygiene_score", 0) for entry in history) / max(total_analyses, 1))

    recent_scans = history[:3]

    food_counts = {}
    for entry in history:
        food = entry.get("main_food", "unknown").title()
        food_counts[food] = food_counts.get(food, 0) + 1

    top_foods = sorted(food_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    weekly_calories = sum(entry.get("calories", 0) for entry in weekly_data)
    weekly_protein = sum(
        next((n["value"] for n in entry.get("nutrition", []) if n["name"] == "protein"), 0)
        for entry in weekly_data
    )

    calorie_progress = min(100, (weekly_calories / (daily_needs["daily_calories"] * 7)) * 100) if weekly_data else 0
    protein_progress = min(100, (weekly_protein / (daily_needs["protein"] * 7)) * 100) if weekly_data else 0

    # ⚠ FIX: DEMO IMAGE PATH SHOULD EXIST IN /static/demo/
    demo_img = "/static/profile.jpg"

    return render_template(
        "index.html",
        total_analyses=total_analyses,
        weekly_scans=weekly_scans,
        avg_calories=avg_calories,
        avg_hygiene=avg_hygiene,
        recent_scans=recent_scans,
        top_foods=top_foods,
        daily_needs=daily_needs,
        calorie_progress=calorie_progress,
        protein_progress=protein_progress,
        demo_img=demo_img,
        profile=profile
    )


@app.route("/recognize")
def recognize():
    return render_template("recognize.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    file = request.files.get("img")
    if not file or not file.filename:
        return "No file uploaded"
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED: ext = ".jpg"
    filename = f"food_{int(datetime.now().timestamp())}{ext}"
    path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)
    session["last_image"] = filename
    return redirect("/predict")

@app.route("/history")
def history_page():
    history_file = os.path.join(BASE_DIR, "history.json")

    if not os.path.exists(history_file) or os.path.getsize(history_file) == 0:
        history = []
    else:
        try:
            history = json.load(open(history_file))
        except:
            history = []

    # Add time_ago
    for item in history:
        ts = item.get("timestamp", "")
        item["time_ago"] = time_ago(ts)

    return render_template("history.html", history=history)

@app.route("/history/view")
def view_history_query():
    item_id = int(request.args.get("id", -1))
    return redirect(f"/history/view/{item_id}")

@app.route("/history/view/<int:item_id>")
def view_each_history(item_id):
    history_file = os.path.join(BASE_DIR, "history.json")
    if not os.path.exists(history_file): return "History not found."
    history = json.load(open(history_file))
    if item_id < 0 or item_id >= len(history): return "Invalid ID."
    item = history[item_id]
    score = item.get("hygiene_score", 0)
    rec = ["Food appears hygienic."] if score >= 60 else ["Low hygiene — be cautious."]
    return render_template("results.html", pack=[item], whole_nutrition=item.get("whole_nutrition", []), recommendations=rec, item_id=item_id)

@app.route("/pdf/view/<int:item_id>")
def pdf_view(item_id):
    history_file = os.path.join(BASE_DIR, "history.json")
    try:
        history = json.load(open(history_file))
        item = history[item_id]
    except:
        return "Error loading history."
    
    pdf_buffer = generate_pdf_report(item)
    return send_file(pdf_buffer, as_attachment=True, download_name=f"NutriScan_{item_id}.pdf", mimetype='application/pdf')

@app.route("/predict")
def predict():
    qty = safe_float(request.args.get("quantity", 100))
    filename = session.get("last_image")
    if not filename: return render_template("results.html", pack=[], whole_nutrition=[], recommendations=[])
    
    full_path = os.path.join(UPLOAD_FOLDER, filename)
    img_bytes = read_bytes(full_path)
    try:
        gem = analyze_with_gemini(img_bytes)
    except Exception as e:
        return f"Gemini error: {e}"

    nut, calories = compute_nutrition(gem["nutrition_per100g"], qty, gem["calories_per100g"])
    
    result = {
        "image": url_for("static", filename=f"uploads/{filename}"),
        "main_food": gem["main_food"],
        "result": {t["label"]: t["score"] for t in gem["top"]},
        "nutrition": nut,
        "quantity": qty,
        "calories": calories,
        "hygiene_score": gem["hygiene_score"],
        "hygiene_reasons": gem["hygiene_reasons"],
    }
    whole = [{"name": "protein", "value": nut[0]["value"]}, {"name": "calcium", "value": nut[1]["value"]},
             {"name": "fat", "value": nut[2]["value"]}, {"name": "carbohydrates", "value": nut[3]["value"]},
             {"name": "vitamins", "value": nut[4]["value"]}]

    # Save History
    history_file = os.path.join(BASE_DIR, "history.json")
    old = []
    if os.path.exists(history_file) and os.path.getsize(history_file) > 0:
        try: old = json.load(open(history_file))
        except: pass
    
    entry = result.copy()
    entry["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry["whole_nutrition"] = whole
    old.insert(0, entry)
    with open(history_file, "w") as f: json.dump(old, f, indent=4)

    return render_template("results.html", pack=[result], whole_nutrition=whole, recommendations=[])

# ============ NEW ROUTES FOR PERSONALIZED INSIGHTS ============

@app.route("/profile", methods=["GET", "POST"])
def profile():
    """User profile management"""
    profile_data = get_user_profile()
    
    if request.method == "POST":
        # Update profile with form data
        profile_data.update({
            "weight": safe_float(request.form.get("weight", 70)),
            "height": safe_float(request.form.get("height", 170)),
            "age": safe_float(request.form.get("age", 30)),
            "gender": request.form.get("gender", "male"),
            "activity_level": request.form.get("activity_level", "moderate"),
            "goal": request.form.get("goal", "maintain")
        })
        save_user_profile(profile_data)
        return redirect("/insights")
    
    return render_template("profile.html", profile=profile_data)

@app.route("/insights")
def insights():
    """Personalized nutrition insights based on 7-day tracking"""
    profile_data = get_user_profile()
    daily_needs = calculate_daily_needs(profile_data)
    weekly_data = get_weekly_nutrition()
    recommendations = generate_personalized_recommendations(weekly_data, daily_needs)
    
    # Calculate weekly totals for display
    weekly_totals = {
        "scans": len(weekly_data),
        "total_calories": sum(entry.get("calories", 0) for entry in weekly_data),
        "avg_hygiene": round(sum(entry.get("hygiene_score", 0) for entry in weekly_data) / max(len(weekly_data), 1), 1)
    }
    
    # Get top foods
    food_counts = {}
    for entry in weekly_data:
        food = entry.get("main_food", "unknown")
        if food in food_counts:
            food_counts[food] += 1
        else:
            food_counts[food] = 1
    
    top_foods = sorted(food_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    
    # Generate charts - USING BASE64 NOW
    pie_url = generate_nutrition_pie_chart(weekly_data)
    
    # Get gallery images
    gallery = [entry.get("image") for entry in weekly_data if entry.get("image")][:10]
    
    insights_data = {
        "summary_cards": {
            "scans": weekly_totals["scans"],
            "total_calories": weekly_totals["total_calories"],
            "avg_hygiene": weekly_totals["avg_hygiene"],
            "top_foods": top_foods
        },
        "pie_url": pie_url,
        "trends_url": None,  # We can add this later
        "gallery": gallery,
        "ai_text": "\n".join(recommendations),
        "daily_needs": daily_needs,
        "profile": profile_data
    }
    
    return render_template("insights.html", data=insights_data)

if __name__ == "__main__":
    print("🚀 NutriScan UI Upgrade Running...")
    app.run(debug=True, port=5000)
# NutriScan - Python Image Nutrition Analyzer

## What This Project Is About
NutriScan is a Python-based application that analyzes a food image and generates a nutrition report. The system preprocesses the uploaded image, predicts the food category using a trained machine learning model, and produces an HTML report containing nutritional information.

---

## How to Set Up

### 1. Clone the Repository
git clone https://github.com/MussaddikKhan/NutriScan-Python-Project.git
cd NutriScan-Python-Project/NutriScan

### 2. Create Virtual Environment
python -m venv venv

### 3. Activate Environment
Windows:
venv\Scripts\activate

Mac/Linux:
source venv/bin/activate

### 4. Install Required Packages
pip install -r requirements.txt

### 5. Run the Project
python app.py

Upload an image and the system will predict the food item and generate the nutrition report.

---

## Features
- Predicts food category from a single uploaded image.
- Generates a clean HTML-based nutrition report.
- Modular Python utilities for preprocessing and prediction.
- Works offline after the model is downloaded.
- Easy to update or replace the existing model.

---

## Future Improvements
- Upgrade to MobileNet or EfficientNet models.
- Add PDF export option.
- Add a better user interface and styling.
- Add API support using FastAPI or Flask.
- Add online or database-based nutrition lookup.
- Add multi-food detection in a single image.
- Add support for multiple languages.

---

## Other Important Notes
- Ensure that the model.h5 file exists in the project folder.
- Supported image formats: JPG and PNG.
- Recommended Python version: 3.8 or higher.
- Clear and well-lit images provide better prediction results.

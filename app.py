from flask import Flask, render_template, request, jsonify, session
import google.generativeai as genai
import json
import re

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Required for session management

# Configure Gemini API
GOOGLE_API_KEY = "AIzaSyBhQoXJHAvup_U4fEzvdAwaPFEgMskT6fA"
genai.configure(api_key=GOOGLE_API_KEY)

# Initialize the model
model = genai.GenerativeModel('gemini-1.5-flash')

# Health assessment questions with scoring criteria
health_questions = [
    {
        "question": "How many hours of sleep do you typically get each night?",
        "scoring": {
            "8-9": 10,
            "7": 8,
            "6": 6,
            "5": 4,
            "<5": 2
        },
        "keywords": ["sleep", "hours", "night", "bedtime"]
    },
    {
        "question": "How many days per week do you engage in physical exercise?",
        "scoring": {
            "5-7": 10,
            "3-4": 8,
            "1-2": 6,
            "0": 2
        },
        "keywords": ["exercise", "workout", "gym", "physical", "sport"]
    },
    {
        "question": "How many servings of fruits and vegetables do you eat daily?",
        "scoring": {
            "5+": 10,
            "3-4": 8,
            "1-2": 6,
            "0": 2
        },
        "keywords": ["fruit", "vegetable", "veggie", "serving", "eat"]
    },
    {
        "question": "How would you rate your stress levels (1-10)?",
        "scoring": {
            "1-3": 10,
            "4-6": 7,
            "7-8": 4,
            "9-10": 2
        },
        "keywords": ["stress", "anxiety", "pressure", "tense"]
    },
    {
        "question": "How many glasses of water do you drink daily?",
        "scoring": {
            "8+": 10,
            "6-7": 8,
            "4-5": 6,
            "2-3": 4,
            "<2": 2
        },
        "keywords": ["water", "drink", "hydrate", "glass"]
    }
]

def extract_number(text):
    # Extract numbers from text
    numbers = re.findall(r'\d+', text)
    if numbers:
        return int(numbers[0])
    return None

def understand_response(response, question):
    # Use Gemini to understand the response
    prompt = f"""Analyze this response to a health question and extract the relevant number or rating.
    Question: {question}
    Response: {response}
    
    Extract the number or rating that answers the question. If no clear number is given, return 'unknown'.
    Only return the number or 'unknown'."""
    
    try:
        result = model.generate_content(prompt)
        return result.text.strip()
    except:
        return "unknown"

def calculate_score(question, answer):
    # First try to extract a number from the answer
    number = extract_number(answer)
    if number is not None:
        for range_str, score in question['scoring'].items():
            if '-' in range_str:
                min_val, max_val = map(int, range_str.split('-'))
                if min_val <= number <= max_val:
                    return score
            elif range_str.startswith('<'):
                if number < int(range_str[1:]):
                    return score
            elif range_str.endswith('+'):
                if number >= int(range_str[:-1]):
                    return score
    
    # If no number found, try to understand the response
    understood_value = understand_response(answer, question['question'])
    if understood_value != "unknown":
        try:
            number = int(understood_value)
            for range_str, score in question['scoring'].items():
                if '-' in range_str:
                    min_val, max_val = map(int, range_str.split('-'))
                    if min_val <= number <= max_val:
                        return score
                elif range_str.startswith('<'):
                    if number < int(range_str[1:]):
                        return score
                elif range_str.endswith('+'):
                    if number >= int(range_str[:-1]):
                        return score
        except:
            pass
    
    # If still no clear answer, return a default score
    return 5

@app.route('/')
def home():
    session['current_question'] = 0
    session['answers'] = []
    session['score'] = 0
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message', '').lower()
    
    if 'current_question' not in session:
        session['current_question'] = 0
        session['answers'] = []
        session['score'] = 0

    if session['current_question'] < len(health_questions):
        # Process answer and calculate score
        if session['current_question'] > 0:  # Skip for first message
            answer = user_message
            question = health_questions[session['current_question'] - 1]
            score = calculate_score(question, answer)
            session['score'] += score
            session['answers'].append({
                'question': question['question'],
                'answer': answer,
                'score': score
            })

        if session['current_question'] < len(health_questions):
            next_question = health_questions[session['current_question']]['question']
            session['current_question'] += 1
            return jsonify({
                'response': next_question,
                'is_question': True,
                'current_question': session['current_question'],
                'total_questions': len(health_questions)
            })
        else:
            # Generate final assessment
            final_score = session['score'] / len(health_questions)
            assessment = generate_final_assessment(session['answers'], final_score)
            session.clear()
            return jsonify({
                'response': assessment,
                'is_question': False,
                'final_score': round(final_score, 1)
            })
    else:
        return jsonify({
            'response': "The assessment is complete. Would you like to start a new assessment?",
            'is_question': False
        })

def generate_final_assessment(answers, final_score):
    prompt = f"""As a professional health and fitness trainer, analyze the following student's health assessment and provide a comprehensive evaluation and personalized training plan:

    Assessment Results:
    {json.dumps(answers, indent=2)}
    
    Final Score: {final_score}/10

    Please provide a detailed response in the following format:

    1. OVERALL ASSESSMENT
    - Brief analysis of their current health status
    - Key strengths and areas for improvement
    - Health score interpretation

    2. PERSONALIZED TRAINING PLAN
    For each area that needs improvement, provide:
    - Specific, actionable steps
    - Weekly goals
    - Exercise recommendations
    - Duration and frequency
    - Progress tracking methods

    3. NUTRITION GUIDANCE
    - Daily meal planning suggestions
    - Portion control tips
    - Healthy snack options
    - Hydration schedule

    4. LIFESTYLE RECOMMENDATIONS
    - Sleep optimization tips
    - Stress management techniques
    - Daily activity suggestions
    - Time management for health

    5. PROGRESS TRACKING
    - Weekly check-in points
    - Key metrics to monitor
    - Success indicators
    - Adjustment criteria

    6. MOTIVATIONAL PLAN
    - Short-term goals
    - Long-term vision
    - Reward system
    - Accountability suggestions

    Keep the tone encouraging and professional, like a personal trainer would speak to their client. Make the recommendations specific and actionable."""
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error generating assessment: {str(e)}"

if __name__ == '__main__':
    app.run(debug=True) 
import os
from flask import Flask, request, jsonify
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
from peft import PeftModel
import torch

# This is a critical line to prevent TensorFlow imports
os.environ['TRANSFORMERS_NO_TF_IMPORT'] = '1'

app = Flask(__name__)
model = None
tokenizer = None
device = None

def load_model():
    """Function to load the model and tokenizer."""
    global model, tokenizer, device
    MODEL_PATH = os.path.join(os.path.dirname(__file__), 'codet5_commenter_final')

    try:
        print("Loading base model...")
        base_model = AutoModelForSeq2SeqLM.from_pretrained("Salesforce/codet5-small")
        
        print("Loading tokenizer from local files...")
        tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
        
        print("Loading LoRA adapters...")
        model = PeftModel.from_pretrained(base_model, MODEL_PATH)
        model = model.merge_and_unload()
        
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        model = model.to(device)
        model.eval()
        print("Model and tokenizer loaded successfully!")
    except Exception as e:
        print(f"Error loading model or tokenizer: {e}")
        model = None
        tokenizer = None

@app.route('/status', methods=['GET'])
def status():
    if model and tokenizer:
        return jsonify({"status": "ready"}), 200
    else:
        return jsonify({"status": "loading"}), 503

@app.route('/generate-comment', methods=['POST'])
def generate_comment():
    if not model or not tokenizer:
        return jsonify({"error": "Model not loaded"}), 503
    
    data = request.get_json()
    if not data or 'code' not in data:
        return jsonify({"error": "No code provided"}), 400
    
    try:
        input_text = f"summarize: {data['code']}"
        inputs = tokenizer(input_text, return_tensors="pt", max_length=512, truncation=True).to(device)
        
        with torch.no_grad():
            outputs = model.generate(
                inputs.input_ids,
                # Increased max_length to get more detailed comments
                max_length=256,
                # Increased num_beams for more diverse and detailed output
                num_beams=6,
                # Set early_stopping to False to encourage longer comments
                early_stopping=False,
                num_return_sequences=1
            )
        
        generated_comment = tokenizer.decode(outputs[0], skip_special_tokens=True)
        return jsonify({"comment": generated_comment})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    load_model()
    app.run(debug=False, use_reloader=False)

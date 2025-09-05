DocuCode: An AI-Powered Code Commenting Tool
Project Description
Docucode is a desktop application that automatically generates descriptive comments for Python code. This tool is designed to enhance code readability and help developers maintain clean, well-documented codebases.

The application uses a fine-tuned deep learning model to understand code logic and produce clear, concise comments for individual functions and classes. It features a modern, intuitive graphical user interface built with PyQt5.

Features
Intelligent Comment Generation: Generates high-quality comments for Python functions and classes.

Local Processing: The AI model runs locally on your machine, ensuring data privacy and offline functionality.

File System Integration: Browse and open .py files directly from within the application.

Dual-Panel Interface: A split-screen layout for viewing both your code and the generated comments side-by-side.

Dark Theme: A professional, high-contrast dark theme for an optimal coding experience.

Getting Started
Prerequisites
Before you begin, ensure you have Python 3.8 or newer installed on your system.

1. Clone the Repository
Start by cloning this repository to your local machine using Git.

git clone https://github.com/0Jos-hua0/Code_Commentor.git

2. Set Up the Environment
It's highly recommended to use a virtual environment to manage dependencies.

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows
venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate

# Install all required packages
pip install -r requirements.txt

3. Download the AI Model
The application uses a fine-tuned CodeT5 model. The model will be automatically downloaded the first time you run the application. This may take a few minutes.

4. Run the Application
The application is a self-contained client-server system. Run the main script to start both the back-end API and the front-end GUI.

python main.py

5. Using DocuCode
Click the "Open Folder" button to load a project directory into the file browser.

Select a .py file from the file browser to open it in the code editor.

Click the "Generate Comment" button to generate comments for each function and class. The comments will appear in the right-hand panel.

The Model
The AI back-end is powered by a CodeT5 model fine-tuned on the CodeSearchNet dataset using the LoRA technique. This approach allows the large language model to run efficiently on local hardware. The model files are approximately 242MB and are automatically downloaded on the first run

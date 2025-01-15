from flask import Flask, request, jsonify, send_file, render_template
from hunyuan_client import HunyuanVideoClient
from flux_s_client import FluxImageClient
from config import load_config
from prompt_generator import PromptGenerator
from datetime import datetime
import random
import os
import time
import json

app = Flask(__name__)
video_client = HunyuanVideoClient()
image_client = FluxImageClient()
prompt_generator = PromptGenerator()

OUTPUT_DIR = r"D:\ComfyUI_windows_portable\ComfyUI\output"

@app.route('/')
def index():
    return render_template('prompt_gen.html')

@app.route('/video_gen')
def video_gen():
    return render_template('video_gen.html')

@app.route('/txt2img_gen')
def txt2img_gen():
    return render_template('txt2img_gen.html')

@app.route('/prompt_gen')
def prompt_gen():
    return render_template('prompt_gen.html')

@app.route('/generate_prompt', methods=['POST'])
def generate_prompt():
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # 데이터 구조 검증
        if not isinstance(data, dict):
            return jsonify({'error': 'Invalid data format'}), 400

        # Target Settings 데이터 확인
        required_fields = ['gender', 'ageGroup', 'productCategory', 'seasonEvent', 'adTone']
        for field in required_fields:
            if field not in data:
                print(f"Missing field: {field}")

        # GPT를 통한 프롬프트 생성
        # prompt_generator.generate는 JSON 문자열을 받도록 되어있음
        generated_prompt = prompt_generator.generate(json.dumps(data))

        return jsonify({
            'success': True,
            'generated_prompt': generated_prompt
        })

    except Exception as e:
        print(f"Error generating prompt: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/generate_examples', methods=['POST'])
def generate_examples():
    data = request.json
    prompt = data.get('prompt')
    folder_name = data.get('savePath', 'flux_examples')
    
    if not prompt:
        return jsonify({'error': 'Prompt is required'}), 400
        
    try:
        # ComfyUI 큐가 처리될 시간을 주기 위해 잠시 대기
        time.sleep(1)
        
        # Generate 4 example images
        image_paths = image_client.generate_images(
            prompt=prompt,
            folder_name=folder_name,
            base_filename="example",
            batch_size=4
        )
        
        # 모든 이미지 파일이 완전히 생성될 때까지 대기
        for path in image_paths:
            while not os.path.exists(path):
                time.sleep(0.5)
            
            # 파일이 완전히 쓰여질 때까지 추가 대기
            time.sleep(1)
        
        # Convert full paths to relative paths for frontend
        relative_paths = [
            os.path.join(folder_name, os.path.basename(path))
            for path in image_paths
        ]
        
        print(f"Generated image paths: {relative_paths}")
        
        return jsonify({
            'success': True,
            'image_paths': relative_paths
        })
    except Exception as e:
        print(f"Error generating images: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/generate', methods=['POST'])
def generate_video():
    data = request.json
    prompt = data.get('prompt')
    use_random_seed = data.get('useRandomSeed')
    frame_length = data.get('frameLength', 73)
    width = data.get('width', 848)
    height = data.get('height', 480)
    folder_name = data.get('savePath', 'KTaivle')
    enable_upscale = data.get('enableUpscale', False)
    seed = None
    
    if not prompt:
        return jsonify({'error': 'Prompt is required'}), 400
        
    if use_random_seed:
        seed = random.randint(1, 999999999999999)
    else:
        try:
            seed = int(data.get('seed'))
            if not (1 <= seed <= 999999999999999):
                return jsonify({'error': 'Seed must be between 1 and 999999999999999'}), 400
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid seed value'}), 400
    
    try:
        # ComfyUI 큐가 처리될 시간을 주기 위해 잠시 대기
        time.sleep(1)
        
        video_path = video_client.generate_video(
            prompt=prompt,
            folder_name=folder_name,
            base_filename="video",
            seed=seed,
            frame_length=frame_length,
            width=width,
            height=height,
            enable_upscale=enable_upscale
        )
        
        # 비디오 생성이 완료될 때까지 대기
        while not os.path.exists(video_path):
            time.sleep(0.5)
            
        # 파일이 완전히 쓰여질 때까지 추가 대기
        time.sleep(2)
        
        filename = os.path.basename(video_path)
        folder = os.path.basename(os.path.dirname(video_path))
        return jsonify({
            'success': True,
            'seed': seed,
            'filename': filename,
            'folder': folder
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/output/<path:filepath>')
def serve_file(filepath):
    base_output_dir = r"D:\ComfyUI_windows_portable\ComfyUI\output"
    
    full_path = os.path.join(base_output_dir, filepath)
    print(f"Serving file from: {full_path}")
    
    if not os.path.exists(full_path):
        print(f"File not found: {full_path}")
        return jsonify({'error': 'File not found'}), 404
    
    try:
        # Determine the mimetype based on file extension
        mimetype = 'video/mp4' if filepath.endswith('.mp4') else 'image/png'
        
        return send_file(
            full_path,
            mimetype=mimetype,
            as_attachment=False,
            download_name=os.path.basename(filepath)
        )
    except Exception as e:
        print(f"Error serving file: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/save_prompt', methods=['POST'])
def save_prompt():
    try:
        data = request.json
        user_id = data.get('userId')
        file_name = data.get('fileName')
        content = data.get('content')

        # 필수 데이터 검증
        if not all([user_id, file_name, content]):
            return jsonify({'error': 'Missing required data'}), 400

        # Prompt 디렉토리 경로 생성
        prompt_dir = os.path.join(OUTPUT_DIR, user_id, 'Prompt')
        os.makedirs(prompt_dir, exist_ok=True)

        # 파일명에 타임스탬프 추가
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        full_file_name = f"{file_name}-{timestamp}.txt"
        file_path = os.path.join(prompt_dir, full_file_name)

        # 파일 저장
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return jsonify({
            'success': True,
            'message': 'Prompt saved successfully',
            'file_name': full_file_name
        }), 200

    except Exception as e:
        print(f"Error saving prompt: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/load_prompts', methods=['GET'])
def load_prompts():
    try:
        user_id = request.args.get('userId')

        if not user_id:
            return jsonify({'error': 'Missing user ID'}), 400

        prompt_dir = os.path.join(OUTPUT_DIR, user_id, 'Prompt')

        # 디렉토리가 없으면 빈 리스트 반환
        if not os.path.exists(prompt_dir):
            return jsonify({'files': []}), 200

        # .txt 파일만 필터링하여 목록 반환
        files = [f for f in os.listdir(prompt_dir) if f.endswith('.txt')]
        # 파일 목록을 날짜순으로 정렬 (최신 순)
        files.sort(reverse=True)

        return jsonify({'files': files}), 200

    except Exception as e:
        print(f"Error loading prompts: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/load_prompt', methods=['GET'])
def load_prompt():
    try:
        user_id = request.args.get('userId')
        file_name = request.args.get('fileName')

        if not all([user_id, file_name]):
            return jsonify({'error': 'Missing required data'}), 400

        file_path = os.path.join(OUTPUT_DIR, user_id, 'Prompt', file_name)

        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404

        # 파일 읽기
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        return jsonify({'content': content}), 200

    except Exception as e:
        print(f"Error loading prompt: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    config = load_config()
    app.run(debug=True, host='0.0.0.0', port=8888)
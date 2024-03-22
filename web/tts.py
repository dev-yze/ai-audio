from flask import Blueprint, current_app, request, redirect, url_for, send_file, Response, stream_with_context
from dao.db import TableInit, VideoWrapper, AudioWrapper, AudioCutWrapper, AudioTextSegmentsWrapper

import os
import whisper
from gtts import gTTS
from datetime import datetime
import re

from config.log import logger
from config.frp import start_frp

from dao.db import TableInit, VideoWrapper, AudioWrapper, AudioCutWrapper, AudioTextSegmentsWrapper
from util.vo import ApiResponse
from util.media import allowed_file, convert_video_sys, mp4_to_audio, extract_audio, extract_wav_audio
from util.secret import md5_str, md5_file

bp_tts = Blueprint('tts', __name__)

@bp_tts.route('/api/tts/hello')
def hello_tts():
    return 'hello! this is tts route'



@bp_tts.route('/audio2text', methods=['POST'])
def audioToText(language='zh'):
    
    file = request.files['file']
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], file.filename)

    if os.path.exists(filepath):
        # 如果文件已经存在，就删除
        os.remove(filepath)
        
    if file and allowed_file(file.filename):
         # 保存文件到指定路径
        file.save(filepath)
        
        initial_prompt = ''
        lan = request.form.get('lan')
        model_size = request.form.get('model')

        if not lan:
            lan = 'en'
        if lan == 'zh':
            initial_prompt = '以下是普通话句子'
        if not model_size:
            model_size = 'medium'
            
        # 加载模型
        model = whisper.load_model(model_size)
        
        result = model.transcribe(filepath, language=lan, initial_prompt=initial_prompt)
        return ApiResponse(200, 'SUCCESS', result['text']).to_json()
    
    else:
        # 返回上传失败的提示信息
        return ApiResponse(-1, '不支持上传格式，目前只支持mp3', None).to_json()




@bp_tts.route('/text2audio', methods=['POST'])
def textToAudio():
    data = request.json
    logger.info(data)
    text = data.get('data')
    lan = data.get('lan')
    filename = data.get('filename')
    if not filename:
        filename = md5_str(text)
    tts = gTTS(text=text, lang=lan)
    timestamp = datetime.now().timestamp()
    filepath = os.path.join(current_app.config['AUDIO_GENERATE'], filename + '_' + str(int(timestamp)) + '.mp3')
    tts.save(filepath)
    return send_file(filepath, mimetype='audio/mp3')

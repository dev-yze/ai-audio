from flask import Blueprint, current_app, request, redirect, url_for, send_file, Response, stream_with_context
from dao.db import TableInit, VideoWrapper, AudioWrapper, AudioCutWrapper, AudioTextSegmentsWrapper

import os
import whisper
from gtts import gTTS
from datetime import datetime
import re

from config.log import logger
from config.frp import start_frp

from dao.db import VideoWrapper, AudioWrapper, AudioCutWrapper, AudioTextSegmentsWrapper
from util.vo import ApiResponse
from util.media import allowed_file, convert_video_sys, mp4_to_audio, extract_audio, extract_wav_audio
from util.secret import md5_file

bp_audio = Blueprint('audio', __name__)

@bp_audio.route('/api/v1/audio/hello')
def hello_audio():
    return 'hello! this is audio route'


# 查询视频音频
@bp_audio.route('/api/v1/audio/videoid/<id>')
def find_audio_by_video_id(id):
    audio_wrapper = AudioWrapper(current_app.config['DB_FILE_PATH'])
    results = audio_wrapper.find_audio_by_video_id(id)
    if results and len(results) > 0:
        return ApiResponse(200, "SUCCESS", dict(results[0])).to_json()
    return ApiResponse(200, "EMPTY", None).to_json()



# 加载视频的音频以及已经剪辑的音频
@bp_audio.route('/api/v1/audio/videoid/list')
def list_audios_by_video_id():
    pass

# 提取音频
@bp_audio.route('/api/v1/video/extract_wav', methods=['POST'])
def extract_wav():
    data = request.json
    video_id = data.get('video_id') 
    rebuild = data.get('rebuild')

    # 获取视频信息，检查视频是否存在  
    video_wrapper = VideoWrapper(current_app.config['DB_FILE_PATH'] )
    video_results = video_wrapper.find_video_by_id(video_id)
    if not video_results or len(video_results) == 0:
        return ApiResponse(-1, '视频信息不存在', None).to_json()

    video_row = dict(video_results[0])
    video_name = video_row.get('file_name')
    # 视频路径
    video_path = video_row.get('file_path')
    if not os.path.exists(video_path):
        return ApiResponse(-1, '视频源文件不存在', None).to_json()

    # 检查音频是否存在
    audio_wrapper = AudioWrapper(current_app.config['DB_FILE_PATH'])
    audio_results = audio_wrapper.find_audio_by_video_id(video_id)
    if len(audio_results) > 0:
        return ApiResponse(200, '音频已经存在', dict(audio_results[0])).to_json()

   
    # 文件名称
    audio_prefix = os.path.basename(video_name).split('.')[0]
    # 输出文件名称
    audio_name = audio_prefix + '.wav'
    # 输出文件路径
    audio_path = os.path.join(current_app.config['UPLOAD_FOLDER'], audio_name)
    logger.info(f'fllepath: {video_path}')
    
    if os.path.exists(audio_path):
        if rebuild:
            os.remove(audio_path)
        else:
            return ApiResponse(200, '音频已经存在了', audio_name).to_json()
    
    try:
        def generate():
            for progress in extract_audio(video_path, audio_path):
                logger.info(f'progress: {progress}')
                if progress == 'finish':
                    audio_md5 = md5_file(audio_path)
                    audio_wrapper.inser_audio(video_id, audio_name, audio_path, audio_md5)
                    audio_results = audio_wrapper.find_audio_by_md5(audio_md5)
                    yield ApiResponse(200, 'WORK', { 'progress': '100.0', 'audio': dict(audio_results[0]) }).to_json()
                else:
                    yield ApiResponse(200, 'WORK', { 'progress': progress, 'audio': None }).to_json()
        return Response(generate(), mimetype="text/event-stream")
        
    except err:
        return ApiResponse(-1, '音频提取失败', None).to_json()



# 截取音频
@bp_audio.route('/api/v1/audio/cut_wav', methods=['POST'])
def cut_wav():
    data = request.json
    audio_id = data.get('audio_id') 
    rebuild = data.get('rebuild')
    start_ms = int(data.get('start_ms'))
    end_ms = int(data.get('end_ms'))
    
    audio_wrapper = AudioWrapper(current_app.config['DB_FILE_PATH'])
    audio_results = audio_wrapper.find_audio_by_id(audio_id)

    if not audio_results or len(audio_results) <= 0:
        return ApiResponse(-1, '音频源文件不存在', None).to_json()
    audio_row = dict(audio_results[0])
    audio_id = audio_row.get('id')
    audio_name = audio_row.get('file_name')
    
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], audio_name)
    if not os.path.exists(filepath):
        return ApiResponse(-1, '音频源文件不存在', None).to_json()

    logger.info(f'fllepath: {filepath}')

    result = extract_wav_audio(filepath, '', start_ms, end_ms)
    cut_path = result.get('path')
    cut_name = result.get('name')
    audio_cut_wrapper = AudioCutWrapper(current_app.config['DB_FILE_PATH'])
    file_md5 = md5_file(cut_path)
    audio_cut_wrapper.inser_audio_cut(audio_id, cut_name, cut_path, file_md5)
    cut_results = audio_cut_wrapper.find_audio_cut_by_md5(file_md5)
    return ApiResponse(200, '音频提取成功', dict(cut_results[0])).to_json()




# 查询剪辑音频
@bp_audio.route('/api/v1/audio/cut/main/<audio_main_id>')
def list_audio_cut_by_ami(audio_main_id):
    audio_cut_wrapper = AudioCutWrapper(current_app.config['DB_FILE_PATH'])
    results = audio_cut_wrapper.list_audio_cut_by_ami(audio_main_id)
    results = [dict(item) for item in results]
    return ApiResponse(200, "SUCCESS", results).to_json()


# 查询剪辑音频
@bp_audio.route('/api/v1/audio/cut/list')
def list_audio_cut():
    audio_cut_wrapper = AudioCutWrapper(current_app.config['DB_FILE_PATH'])
    results = audio_cut_wrapper.list_audio_cut()
    results = [dict(item) for item in results]
    return ApiResponse(200, "SUCCESS", results).to_json()



# 删除剪辑音频
@bp_audio.route('/api/v1/audio/cut/del/<id>')
def del_audio_cut(id):
    logger.info(f'id = {id}')
    audio_cut_wrapper = AudioCutWrapper(current_app.config['DB_FILE_PATH'])
    results = audio_cut_wrapper.find_audio_cut_by_id(id)
    if len(results) == 0:
        return ApiResponse(-1, "视频不存在", None).to_json()
    audio_cut = dict(results[0])
    logger.info(f'audio_cut = {audio_cut}')
    file_path = audio_cut.get('file_path')
    if os.path.exists(file_path):
        os.remove(file_path)
    audio_cut_wrapper.del_by_id(id)
    return ApiResponse(200, "SUCCESS", None).to_json()



# 音频转文本
@bp_audio.route('/api/v1/audio/extract/text', methods=['POST'])
def audioExtractText():
    audio_id = request.json.get('audio_id')
    model_size = request.json.get('model_size')
    lan = request.json.get('lan')

    audio_cut_wrapper = AudioCutWrapper(current_app.config['DB_FILE_PATH'])
    audio_results = audio_cut_wrapper.find_audio_cut_by_id(audio_id)

    if not audio_results or len(audio_results) <= 0:
        return ApiResponse(-1, '音频记录不存在', None).to_json()

    if not model_size:
        model_size = 'medium'

    audio_row = dict(audio_results[0])
    logger.info(f'audio_row = {audio_row}')
    id = audio_row.get('id')
    file_path = audio_row.get('file_path')

    if not os.path.exists(file_path):
        return ApiResponse(-1, '音频文件不存在', None).to_json()

    if not lan:
        lan = 'en'
    elif lan == 'zh':
        initial_prompt = '以下是普通话句子'
        
    # 检查音频文件大小，最好不要太大
    
    # 加载模型
    model = whisper.load_model(model_size)
    result = model.transcribe(file_path, language=lan, initial_prompt=initial_prompt)
    logger.info(f"reslut.text = {result['text']}")

    if not audio_row['trans_text']:
        # 更新下音频文本
        audio_cut_wrapper.update_audio_cut_text(id, result['text'], result['language'])

    audio_text_segments_wrapper = AudioTextSegmentsWrapper(current_app.config['DB_FILE_PATH'])
    ats_results = audio_text_segments_wrapper.list_by_audio_id(id)
    if not ats_results or len(ats_results) == 0:
        for item in result['segments']:
            audio_text_segments_wrapper.inser_audio_text_segments(audio_id, item)
    audio_results = audio_cut_wrapper.find_audio_cut_by_id(audio_id)
    return ApiResponse(200, 'SUCCESS', dict(audio_results[0])).to_json()


@bp_audio.route('/api/v1/audio/stream/<path:filepath>')
def audio_stream(filepath):
    def generate():
        with open(filepath, "rb") as fwave:
            data = fwave.read(1024)
            while data:
                yield data
                data = fwave.read(1024)
    return Response(generate(), mimetype="audio/x-wav")


@bp_audio.route('/api/v1/audio/text/segments/<audio_id>')
def list_audio_text_segments(audio_id):
    audio_text_segments_wrapper = AudioTextSegmentsWrapper(current_app.config['DB_FILE_PATH'])
    results = audio_text_segments_wrapper.list_by_audio_id(audio_id=audio_id)
    return ApiResponse(200, 'SUCCESS', [dict(item) for item in results]).to_json()
    
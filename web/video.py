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

bp_video = Blueprint('video', __name__)

@bp_video.route('/api/v1/video/hello')
def hello_video():
    return 'hello! this is video route'



@bp_video.route('/api/v1/video/md5/<md5>')
def find_video(md5):
     video_wrapper = VideoWrapper(current_app.config['DB_FILE_PATH'])
     results = video_wrapper.find_video_by_md5(md5=md5)
     if results and len(results) > 1:
         return ApiResponse(200, "SUCCESS", dict(results[0])).to_json()
     return ApiResponse(200, "EMPTY", None).to_json()


@bp_video.route('/api/v1/video/list', methods=['POST'])
def list_video():
    video_wrapper = VideoWrapper(current_app.config['DB_FILE_PATH'])
    results = video_wrapper.list_video()
    results = [dict(item) for item in results]
    return ApiResponse(200, "SUCCESS", results).to_json()


# 上传视频
@bp_video.route('/api/v1/video/upload', methods=['POST'])
def uploadVideo():
    '''
        上传视频
        chunk: 分片文件
        cur: 当前分片索引
        total: 分片大小
        cmd5: 分片文件md5
        md5: 文件md5
        filename: 分片文件名称
    '''
    chunk = request.files['chunk']
    cur = int(request.form.get('cur'))
    total = int(request.form.get('total'))
    cmd5 = request.form.get('cmd5')
    md5 = request.form.get('md5')
    filename = request.form.get('filename')
    logger.info(f'cur={cur},total={total},cmd5={cmd5},md5={md5},filename={filename}')

    # 参数校验
    if not chunk:
        return ApiResponse(-1, '文件不存在', None).to_json()

    video_wrapper = VideoWrapper(current_app.config['DB_FILE_PATH'])
    # 检查文件是否已经存在
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        # return ApiResponse(-1, '文件已经存在', None).to_json()

    # 保存分片文件，临时存在上传路径/temp/md5
    chunk_dir_path = os.path.join(current_app.config['UPLOAD_FOLDER'], f'temp/{md5}')
    if not os.path.exists(chunk_dir_path):
        os.makedirs(chunk_dir_path)
    chunk_file_path = os.path.join(chunk_dir_path, f'part_{cur}')
    if not os.path.exists(chunk_file_path):
        chunk.save(chunk_file_path)

    if cur == (total - 1):
        # 合并分片文件
        with open(filepath, 'wb') as final_file:
            for findex in range(total):
                chunk_path = os.path.join(chunk_dir_path, f'part_{findex}')
                with open(chunk_path, 'rb') as chunk_file:
                    final_file.write(chunk_file.read())
                os.remove(chunk_path)
            try:
                os.rmdir(chunk_dir_path)
            except OSError as e:
                logger.info(f'delete dir err, dir = {chunk_dir_path}')
        
        video_wrapper.inser_video(file_name=filename, file_path=filepath, md5=md5)
        results = video_wrapper.find_video_by_md5(md5=md5)
        logger.info(dict(results[0]))
        # 将文件信息保存到数据库
        return ApiResponse(200, '文件上传成功', dict(results[0])).to_json()
    return ApiResponse(200, '分片文件保存成功', filepath).to_json()



# 获取视频流
@bp_video.route('/api/v1/video/stream/<string:filename>')
def video_stream(filename):
    video_wrapper = VideoWrapper(current_app.config['DB_FILE_PATH'] )
    results = video_wrapper.find_video_by_filename(filename)
    if not results:
        return ApiResponse(-1, '视频记录不存在', None).to_json()
    video_row = dict(results[0])
    file_path = os.path.join(video_row['file_path'])
    if not os.path.exists(file_path):
        return ApiResponse(-1, '视频文件不存在', None).to_json()

    range_hander = request.headers.get('Range', None)
    
    if not range_hander:
        
        def generate():
            with open(file_path, 'rb') as video_file:
                while True:
                    chunk = video_file.read(1024*1024)
                    if not chunk:
                        break
                    yield chunk

        return Response(stream_with_context(generate()), mimetype='video/mp4')

    else:
        logger.info(f'range_hander = {range_hander}')
        size = os.path.getsize(file_path)
        byte1, byte2 = 0, None
        m = re.search('(\d+)-(\d*)', range_hander)
        g = m.groups()

        byte1, byte2 = int(g[0]), g[1]
        byte2 = int(byte2) if byte2 else size - 1

        length = byte2 - byte1 + 1
        data = None
        with open(file_path, 'rb') as f:
            f.seek(byte1)
            data = f.read(length)

        rv = Response(data, 206, mimetype='video/mp4', content_type='video/mp4', direct_passthrough=True)
        rv.headers.add('Content-Range', f'bytes {byte1}-{byte2}/{size}')
        rv.headers.add('Accept-Ranges', 'bytes')
        return rv


# 将指定文件转为mp4类型
@bp_video.route('/api/v1/video/parse_mp4', methods=['POST'])
def parse_mp4():
    '''
        filename: 文件名称
        rebuild: 如果为True,则不管存在都重新生成, false则存在就不重新生成
    '''
    data = request.json
    filename = data.get('filename') 
    rebuild = data.get('rebuild')
    
    video_wrapper = VideoWrapper(current_app.config['DB_FILE_PATH'] )
    results = video_wrapper.find_video_by_filename(filename)
    if not results or len(results) == 0:
        return ApiResponse(-1, '视频信息不存在', None).to_json()

    video_row = dict(results[0])
    # filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    filepath = video_row.get('file_path')
    if not os.path.exists(filepath):
        return ApiResponse(-1, '视频源文件不存在', None).to_json()
    
    file_name_prefix = os.path.basename(filename).split('.')[0]
    parse_file_name = file_name_prefix + '.mp4'
    parse_file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], parse_file_name)
    logger.info(f'fllepath: {filepath}')
    mp4_results = video_wrapper.find_video_by_filename(parse_file_name)
    if mp4_results and len(mp4_results) > 0:
        return ApiResponse(200, '转换成功', dict(mp4_results[0])).to_json()

    
    try:
        def generate():
            for progress in convert_video_sys(filepath, parse_file_path):
                if progress.startswith('100.'):
                    new_md5 = md5_file(parse_file_path)
                    video_wrapper.update_video(parse_file_name, parse_file_path, new_md5, video_row.get('id'))
                    mp4_results = video_wrapper.find_video_by_md5(new_md5)
                    yield ApiResponse(200, 'WORK', { 'progress': progress, 'video': dict(mp4_results[0]) }).to_json()
                else:
                    yield ApiResponse(200, 'WORK', { 'progress': progress, 'video': None }).to_json()
        return Response(generate(), mimetype="text/event-stream")
    except err:
        return ApiResponse(-1, '视频转换失败', None).to_json()

import ffmpeg
import subprocess
import re
import sys
import os
from secret import md5_str, md5_file
import whisper
from db import TableInit, VideoWrapper, AudioWrapper, AudioCutWrapper, AudioTextSegmentsWrapper
from vo import ApiResponse
from media import convert_to_mp4, convert_video_sys, mp4_to_audio, extract_audio, extract_wav_audio
import argparse 

def cut_wav():
    audio_id = 14 
    start_ms = 324683
    end_ms = 822531
    
    audio_wrapper = AudioWrapper('./db/media.db')
    audio_results = audio_wrapper.find_audio_by_video_id(audio_id)

    if not audio_results or len(audio_results) <= 0:
        return ApiResponse(-1, '音频源文件不存在', None).to_json()
    audio_row = dict(audio_results[0])
    audio_id = audio_row.get('id')
    audio_name = audio_row.get('file_name')
    
    filepath = os.path.join('./upload', audio_name)
    if not os.path.exists(filepath):
        return ApiResponse(-1, '音频源文件不存在', None).to_json()

    print(f'fllepath: {filepath}')

    result = extract_wav_audio(filepath, '', start_ms, end_ms)
    print(result)
    # print(name)
    # audio_cut_wrapper = AudioCutWrapper(app.config['DB_FILE_PATH'])
    file_md5 = md5_file(result.get('path'))
    # audio_cut_wrapper.inser_audio_cut(audio_id, name, path, file_md5)
    # cut_results = audio_cut_wrapper.find_audio_cut_by_md5(file_md5)
    return ApiResponse(200, '音频提取成功', None).to_json()


# cut_wav()

# 音频转文本
def audioExtractText():
    audio_id = 5
    # 主音频还是剪切音频
    audio_type = ''
    model_size = 'large'
    lan = 'zh'

    audio_cut_wrapper = AudioCutWrapper('./db/media.db')
    audio_results = audio_cut_wrapper.find_audio_cut_by_id(audio_id)
        
    if not audio_results or len(audio_results) <= 0:
        return ApiResponse(-1, '音频记录不存在', None).to_json()

    if not model_size:
        model_size = 'medium'

    audio_row = dict(audio_results[0])
    file_path = audio_row.get('file_path')

    if not lan:
        lan = 'en'
    if lan == 'zh':
        initial_prompt = '以下是普通话句子'

    if not os.path.exists(file_path):
        return ApiResponse(-1, '音频文件不存在', None).to_json()

    # 加载模型
    model = whisper.load_model(model_size)
    result = model.transcribe(file_path, language=lan, initial_prompt=initial_prompt)
    print(f"翻译文本:\n {result['text']}")
    print(f"language: {result['language']}")
    if not audio_row['trans_text']:
        audio_cut_wrapper.update_audio_cut_text(audio_row['id'], result['text'], result['language'])
    audio_text_segments_wrapper = AudioTextSegmentsWrapper('./db/media.db')
    # for item in result['segments']:
        # print('\n\n')
        # print(f"id: {item['id']}")
        # print(f"seek: {item['seek']}")
        # print(f"start-end: {item['start']}-{item['end']}")
        # print(f"text: {item['text']}")
        # print(f"tokens: {item['tokens']}")
        # print(f"temperature: {item['temperature']}")
        # print(f"avg_logprob: {item['avg_logprob']}")
        # print(f"compression_ratio: {item['compression_ratio']}")
        # print(f"no_speech_prob: {item['no_speech_prob']}")
        # print(item)
        # audio_text_segments_wrapper.inser_audio_text_segments(audio_id, item)

    results = audio_text_segments_wrapper.list_by_audio_id(audio_id=audio_id)
    for item in results:
        print(dict(item))
    # return ApiResponse(200, 'success', result['text']).to_json()


# audioExtractText()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-frp", type=bool, default=False,help="open frp")
    parser.add_argument('-dbinit', type=bool, default=False, help="clear db, start new project")
    parser.add_argument('-model', type=str, default='large', help="load whisper model")
    parser.add_argument('--processes', type=int, default=0, help="cpu_processes")

    args, _ = parser.parse_known_args()

    print(f'frp:{args.frp}')
    print(f'dbinit:{args.dbinit}')
    print(f'model:{args.model}')
    print(f'processes:{args.processes}')
    if args.frp:
        print('执行frp程序')
    if args.dbinit:
        print('执行数据库初始程序')
    
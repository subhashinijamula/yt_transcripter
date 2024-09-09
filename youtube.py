import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import pandas as pd
import os
import zipfile
from io import BytesIO
import tempfile

def get_video_id_from_url(url):
    if 'youtube.com/watch?v=' in url:
        return url.split('v=')[1].split('&')[0]
    elif 'youtu.be/' in url:
        return url.split('youtu.be/')[1].split('?')[0]
    elif 'youtube.com/shorts/' in url:
        return url.split('shorts/')[1].split('?')[0]
    else:
        raise ValueError("URL is not a valid YouTube URL")

def format_transcript_as_paragraph(transcript):
    return ' '.join([segment['text'] for segment in transcript])

def fetch_transcript(video_id, language_code):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[language_code])
        return format_transcript_as_paragraph(transcript)
    except NoTranscriptFound:
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            if transcript_list.find_manually_created_transcript([language_code]):
                st.warning(f"Transcript not found in {language_code}.")
            if 'en' in transcript_list._manually_created_transcripts:
                st.warning("Falling back to English transcript.")
                transcript = transcript_list.find_manually_created_transcript(['en'])
                return format_transcript_as_paragraph(transcript.fetch())
            else:
                available_transcripts = transcript_list._manually_created_transcripts or transcript_list._generated_transcripts
                if available_transcripts:
                    transcript = transcript_list.find_transcript(available_transcripts)
                    st.warning(f"Falling back to {transcript.language} transcript.")
                    return format_transcript_as_paragraph(transcript.fetch())
                else:
                    return f"No transcripts available for video ID {video_id}."
        except TranscriptsDisabled:
            return f"Transcripts are disabled for video ID {video_id}."
        except Exception as e:
            return f"Error fetching fallback transcript for video ID {video_id}: {e}"
    except TranscriptsDisabled:
        return f"Transcripts are disabled for video ID {video_id}."
    except Exception as e:
        return f"Error for video ID {video_id}: {e}"

def save_transcripts_to_folder(urls, language_code, folder_path):
    processed_videos = 0
    for url in urls:
        try:
            video_id = get_video_id_from_url(url)
            transcript = fetch_transcript(video_id, language_code)
            
            if transcript.startswith("Error") or "No transcript" in transcript or "Transcripts are disabled" in transcript:
                st.warning(transcript)  
                continue
            file_name = f"{video_id}_transcript.txt"
            file_path = os.path.join(folder_path, file_name)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(transcript)
            processed_videos += 1
        except Exception as e:
            st.error(f"Error processing {url}: {e}")
            continue
    return processed_videos

def zip_folder(folder_path):
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                zf.write(file_path, os.path.relpath(file_path, folder_path))
    zip_buffer.seek(0)
    return zip_buffer
st.title('YouTube Transcript Converter')
url = st.text_input('Enter YouTube URL (optional):')
uploaded_file = st.file_uploader('Upload Excel file containing URLs', type=['xlsx'])
language_options = {
    'English': 'en',
    'Telugu': 'te',
    'Hindi': 'hi',
    'Tamil': 'ta',
    'Kannada': 'kn',
}
selected_language = st.selectbox('Select Language', list(language_options.keys()))

if selected_language:
    language_code = language_options[selected_language]
    
    if url:
        transcript = fetch_transcript(get_video_id_from_url(url), language_code)
        st.subheader('Transcript:')
        st.write(transcript)
    
    if uploaded_file:
        df = pd.read_excel(uploaded_file)
        
        if 'URL' in df.columns:
            urls = df['URL'].dropna().tolist()

            with tempfile.TemporaryDirectory() as temp_folder:
                processed_videos = save_transcripts_to_folder(urls, language_code, temp_folder)
                
                if processed_videos == 0:
                    st.error("No transcripts were available for the provided URLs.")
                else:
                    zip_buffer = zip_folder(temp_folder)
                    st.success(f"Transcripts for {processed_videos} videos have been processed.")
                    st.download_button(
                        label="Download Transcripts Zip",
                        data=zip_buffer.getvalue(),
                        file_name="transcripts.zip",
                        mime="application/zip"
                    )
        else:
            st.error("Uploaded file does not contain a 'URL' column.")
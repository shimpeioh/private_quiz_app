import streamlit as st
import google.generativeai as genai
import random
from pathlib import Path



# Gemini APIの設定
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# モデルの設定
model = genai.GenerativeModel('gemini-1.5-flash-002')

# セッション初期化
if 'japanese_text' not in st.session_state:
    st.session_state.japanese_text = None
if 'english_text' not in st.session_state:
    st.session_state.english_text = None
if 'quiz_sentence' not in st.session_state:
    st.session_state.quiz_sentence = None
if 'file_uploaded' not in st.session_state:
    st.session_state.file_uploaded = False
if 'english_converted' not in st.session_state:
    st.session_state.english_converted = False

def reset_english_session():
    st.session_state.japanese_text = None
    st.session_state.english_text = None
    st.session_state.quiz_sentence = None
    st.session_state.english_converted = False

def convert_to_english(japanese_text, target_score):
    prompt = f"""
    以下の日本語をTOEIC {target_score}点レベルの英語に変換してください。
    できるだけ自然な英語で、{target_score}点レベルに適した語彙と文法を使用してください。

    日本語テキスト:
    {japanese_text}
    """
    return model.generate_content(prompt).text

def create_quiz(english_text):
    sentences = [s.strip() for s in english_text.split('.') if s.strip()]
    return random.choice(sentences)

def evaluate_translation(original_english, japanese_answer):
    prompt = f"""
    以下の英文に対する日本語訳を評価してください。
    100点満点で採点し、改善点があれば指摘してください。

    英文: {original_english}
    提出された日本語訳: {japanese_answer}
    
    形式:
    点数: [数字のみ]
    コメント: [評価コメント]
    """
    return model.generate_content(prompt).text

def extract_vocabulary(english_text):
    prompt = f"""
    以下の英文から重要な単語と熟語を抽出してください。
    各項目に日本語訳も付けてください。

    英文:
    {english_text}
    
    形式:
    単語/熟語 - 日本語訳
    """
    return model.generate_content(prompt).text

def main():
    st.title("TOEIC英語学習アプリ")
    
    target_score = st.number_input("目標TOEICスコアを入力してください", 
                                 min_value=10, 
                                 max_value=990, 
                                 value=700,
                                 step=10)
    
    uploaded_file = st.file_uploader("日本語のテキストファイルをアップロードしてください", 
                                   type=['txt'],
                                   on_change=reset_english_session)
    
    if uploaded_file and not st.session_state.file_uploaded:
        with st.spinner('ファイルを読み込んでいます...'):
            st.session_state.japanese_text = uploaded_file.read().decode('utf-8')
            st.session_state.file_uploaded = True
        st.success('読み込み完了')
        
    if st.session_state.file_uploaded and not st.session_state.english_converted:
        if st.button("英語に変換"):
            with st.spinner('英語に変換中...'):
                st.session_state.english_text = convert_to_english(
                    st.session_state.japanese_text, 
                    target_score
                )
                st.session_state.english_converted = True
            st.success('変換完了')
    
    if st.session_state.english_converted:
        if not st.session_state.quiz_sentence or st.button("新しい問題を出題"):
            with st.spinner('問題を作成中...'):
                st.session_state.quiz_sentence = create_quiz(st.session_state.english_text)
            
        st.subheader("翻訳問題")
        st.write("以下の英文を日本語に訳してください：")
        st.write(st.session_state.quiz_sentence)
        
        user_translation = st.text_area("あなたの訳", "")
        if st.button("採点する") and user_translation:
            with st.spinner('採点中...'):
                evaluation = evaluate_translation(
                    st.session_state.quiz_sentence, 
                    user_translation
                )
            st.write("評価結果:")
            st.write(evaluation)
        
        if st.checkbox("単語・熟語リストを表示"):
            with st.spinner('単語・熟語を抽出中...'):
                vocabulary = extract_vocabulary(st.session_state.english_text)
            st.subheader("重要な単語・熟語リスト")
            st.write(vocabulary)

if __name__ == "__main__":
    main()

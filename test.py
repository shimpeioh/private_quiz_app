import streamlit as st
import google.generativeai as genai
import random
from pathlib import Path
import hmac


# Gemini APIの設定
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# モデルの設定
model = genai.GenerativeModel('gemini-1.5-flash-002')

# パスワード検証関数
def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if hmac.compare_digest(st.session_state["password"], st.secrets["password"]):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # パスワードをセッションステートから削除
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show input for password.
        st.text_input(
            "パスワードを入力してください", type="password", on_change=password_entered, key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        # Password incorrect, show input + error.
        st.text_input(
            "パスワードを入力してください", type="password", on_change=password_entered, key="password"
        )
        st.error("😕 パスワードが違います")
        return False
    else:
        # Password correct.
        return True
def init_session_state():
    states = {
        'japanese_text': None,
        'english_text': None,
        'quiz_sentence': None,
        'file_uploaded': False,
        'english_converted': False,
        'keywords': '',
        'word_count': 200
    }
    for key, value in states.items():
        if key not in st.session_state:
            st.session_state[key] = value

def reset_session():
    for key in st.session_state:
        if key != 'target_score':  # Preserve target score
            st.session_state[key] = None if not isinstance(st.session_state[key], bool) else False
    st.session_state.word_count = 200
    st.session_state.keywords = ''

def regenerate_text():
    st.session_state.english_text = None
    st.session_state.quiz_sentence = None
    st.session_state.english_converted = False

def generate_long_text(keywords, target_score, word_count):
    prompt = f"""
    Create an English text about the following keywords: {keywords}
    Requirements:
    - Use vocabulary and grammar suitable for TOEIC {target_score} level
    - Text should be approximately {word_count} words long
    - Use natural, flowing English
    """
    return model.generate_content(prompt).text

# Existing functions remain unchanged
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
    採点では単語/熟語と文法の取り扱いに重点を置いてください。

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
    init_session_state()
    
    st.sidebar.number_input(
        "目標TOEICスコアを入力してください",
        min_value=10, max_value=990, value=700, step=10,
        key='target_score'
    )

    col1, col2 = st.sidebar.columns(2)
    if col1.button("リセット"):
        reset_session()
        st.rerun()
    if col2.button("再生成") and st.session_state.english_converted:
        regenerate_text()
        st.rerun()

    tab1, tab2 = st.tabs(["短文翻訳", "長文翻訳"])

    with tab1:
        # Original short text translation functionality
        uploaded_file = st.file_uploader(
            "日本語のテキストファイルをアップロードしてください",
            type=['txt'],
            on_change=reset_session
        )

        if uploaded_file and not st.session_state.file_uploaded:
            with st.spinner('ファイルを読み込んでいます...'):
                st.session_state.japanese_text = uploaded_file.read().decode('utf-8')
                st.session_state.file_uploaded = True
            st.success('読み込み完了')
        
        # Rest of original functionality...
        if st.session_state.file_uploaded and not st.session_state.english_converted:
            if st.button("英語に変換", key="convert_short"):
                with st.spinner('英語に変換中...'):
                    st.session_state.english_text = convert_to_english(
                        st.session_state.japanese_text,
                        st.session_state.target_score,
                    )
                    st.session_state.english_converted = True
                st.success('変換完了')

        if st.session_state.english_converted:
            handle_translation_quiz("short")

    with tab2:
        keywords = st.text_input("テキストのキーワードを入力してください（カンマ区切り）", 
                               key='keywords')
        word_count = st.number_input("生成する文章の単語数", 
                                   min_value=50, max_value=500, value=200, step=50,
                                   key='word_count')
        
        if st.button("長文を生成", key="generate_long_button"):
            with st.spinner('長文を生成中...'):
                st.session_state.english_text = generate_long_text(
                    keywords, 
                    st.session_state.target_score,
                    word_count
                )
                st.session_state.english_converted = True
            st.success('生成完了')
            st.write(st.session_state.english_text)
            handle_translation_quiz("long")

        elif st.session_state.english_converted:
            st.write(st.session_state.english_text)
            handle_translation_quiz("long")

def handle_translation_quiz(tab_name):
    if not st.session_state.quiz_sentence or st.button("新しい問題を出題", key=f"new_quiz_button_{tab_name}"):
        with st.spinner('問題を作成中...'):
            st.session_state.quiz_sentence = create_quiz(st.session_state.english_text)
    
    st.subheader("翻訳問題")
    st.write("以下の英文を日本語に訳してください：")
    st.write(st.session_state.quiz_sentence)
    
    user_translation = st.text_area("あなたの訳", "", key=f"translation_input_{tab_name}")
    if st.button("採点する", key=f"grade_button_{tab_name}") and user_translation:
        with st.spinner('採点中...'):
            evaluation = evaluate_translation(
                st.session_state.quiz_sentence,
                user_translation
            )
        st.write("評価結果:")
        st.write(evaluation)
    
    if st.checkbox("単語・熟語リストを表示", key=f"sentense_list_{tab_name}"):
        with st.spinner('単語・熟語を抽出中...'):
            if tab_name == "short":
                vocabulary = extract_vocabulary(st.session_state.quiz_sentence)
            elif tab_name == "long":
                vocabulary = extract_vocabulary(st.session_state.english_text)
        st.subheader("重要な単語・熟語リスト")
        st.write(vocabulary)
        
if __name__ == "__main__":
    if check_password():
        main()

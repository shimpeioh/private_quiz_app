import streamlit as st
import pandas as pd
import random
import hmac
import google.generativeai as genai
import json

# ページ設定
st.set_page_config(
    page_title="英文問題生成アプリ",
    page_icon="📚",
    layout="wide"
)

# Gemini APIの設定
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
# Gemini 2.0 Flash Experimentalモデルの設定
model = genai.GenerativeModel('gemini-2.0-flash-exp')

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

def load_csv_words(csv_name):
    """CSVファイルからA列の英単語を読み込む"""
    try:
        df = pd.read_csv(csv_name)
        # A列（最初の列）の単語を取得し、NaNを除外
        words = df.iloc[:, 0].dropna().tolist()
        return words
    except FileNotFoundError:
        st.error(f"CSVファイル '{csv_name}' が見つかりません。")
        return []
    except Exception as e:
        st.error(f"CSVファイルの読み込みエラー: {e}")
        return []

def generate_problems_with_gemini(words, sentence_pattern, num_questions, format_type):
    """Gemini APIを使用して英文問題を生成"""
    
    # プロンプトの作成
    format_instruction = "記述形式" if format_type == "記述形式" else "並び替え"
    
    prompt = f"""
以下の条件に基づいて英文問題を{num_questions}問作成してください：

条件：
- 文型: {sentence_pattern}
- 使用単語: {', '.join(words)}（各問題で1つずつ必ず使用）
- 問題形式: {format_instruction}
- 各問題には日本語訳を付ける

{format_instruction}の場合の出力形式：
{
  "problems": [
    {
      "word": "使用した英単語",
      "japanese": "日本語訳",
      "english": "正解の英文",
      "scrambled": "並び替え用の単語リスト（並び替えの場合のみ）"
    }
  ]
}

注意事項：
- 文型 {sentence_pattern} に必ず従ってください
- 各問題で指定された単語を必ず使用してください
- 自然で実用的な英文を作成してください
- JSON形式で回答してください
"""

    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # JSONの抽出（```json と ``` で囲まれている場合の処理）
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            response_text = response_text[json_start:json_end].strip()
        elif "```" in response_text:
            json_start = response_text.find("```") + 3
            json_end = response_text.rfind("```")
            response_text = response_text[json_start:json_end].strip()
        
        problems_data = json.loads(response_text)
        return problems_data["problems"]
    
    except json.JSONDecodeError as e:
        st.error(f"JSONの解析エラー: {e}")
        st.write("生成されたテキスト:", response_text)
        return []
    except Exception as e:
        st.error(f"問題生成エラー: {e}")
        return []

def initialize_session_state():
    """セッションステートの初期化"""
    if "problems" not in st.session_state:
        st.session_state.problems = []
    if "show_answers" not in st.session_state:
        st.session_state.show_answers = False
    if "user_answers" not in st.session_state:
        st.session_state.user_answers = {}

def main():
    if not check_password():
        return
    
    st.title("📚 英文問題生成アプリ")
    st.markdown("---")
    
    # セッションステートの初期化
    initialize_session_state()
    
    # サイドバーでの入力設定
    with st.sidebar:
        st.header("⚙️ 設定")
        
        # CSV選択
        csv_options = ["A1_word.csv", "A2_word.csv", "B1_word.csv", "B2_word.csv"]
        selected_csv = st.selectbox("📄 CSV名", csv_options)
        
        # 文型選択
        sentence_patterns = ["SVO", "SVC", "SVOO", "SVOC"]
        selected_pattern = st.selectbox("📝 文型", sentence_patterns)
        
        # 問題数選択
        num_questions = st.slider("🔢 問題数", min_value=1, max_value=5, value=3)
        
        # 問題形式選択
        format_options = ["記述形式", "並び替え"]
        selected_format = st.radio("📋 問題形式", format_options)
        
        st.markdown("---")
        
        # 生成ボタン
        if st.button("🎯 問題生成", type="primary", use_container_width=True):
            with st.spinner("問題を生成中..."):
                # CSVから単語を読み込み
                all_words = load_csv_words(selected_csv)
                
                if all_words:
                    # ランダムに単語を選択
                    selected_words = random.sample(all_words, min(num_questions, len(all_words)))
                    
                    # Geminiで問題生成
                    problems = generate_problems_with_gemini(
                        selected_words, selected_pattern, num_questions, selected_format
                    )
                    
                    if problems:
                        st.session_state.problems = problems
                        st.session_state.show_answers = False
                        st.session_state.user_answers = {}
                        st.success("問題が生成されました！")
                        st.rerun()
                    else:
                        st.error("問題生成に失敗しました。")
    
    # メイン表示エリア
    if st.session_state.problems:
        st.header("📖 英文問題")
        
        # 各問題の表示
        for i, problem in enumerate(st.session_state.problems):
            with st.container():
                st.subheader(f"問題 {i+1}")
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.write(f"**使用単語:** {problem['word']}")
                    st.write(f"**日本語:** {problem['japanese']}")
                
                with col2:
                    if not st.session_state.show_answers:
                        if selected_format == "記述形式":
                            user_answer = st.text_input(
                                "英文を入力:",
                                key=f"answer_{i}",
                                placeholder="英文を入力してください"
                            )
                            st.session_state.user_answers[i] = user_answer
                        else:  # 並び替え
                            if "scrambled" in problem:
                                scrambled_words = problem["scrambled"]
                                st.write("**単語を並び替えてください:**")
                                st.write(" | ".join(scrambled_words))
                                
                                user_answer = st.text_input(
                                    "並び替えた英文:",
                                    key=f"answer_{i}",
                                    placeholder="単語を並び替えて入力"
                                )
                                st.session_state.user_answers[i] = user_answer
                
                # 正解表示
                if st.session_state.show_answers:
                    st.write(f"**正解:** {problem['english']}")
                    
                    if i in st.session_state.user_answers:
                        user_ans = st.session_state.user_answers[i].strip()
                        correct_ans = problem['english'].strip()
                        
                        if user_ans.lower() == correct_ans.lower():
                            st.success(f"✅ あなたの答え: {user_ans}")
                        else:
                            st.error(f"❌ あなたの答え: {user_ans}")
                
                st.markdown("---")
        
        # 答え合わせボタン
        if not st.session_state.show_answers:
            if st.button("📊 答え合わせ", type="secondary", use_container_width=True):
                st.session_state.show_answers = True
                st.rerun()
        else:
            # 正解数の表示
            correct_count = 0
            total_questions = len(st.session_state.problems)
            
            for i, problem in enumerate(st.session_state.problems):
                if i in st.session_state.user_answers:
                    user_ans = st.session_state.user_answers[i].strip()
                    correct_ans = problem['english'].strip()
                    if user_ans.lower() == correct_ans.lower():
                        correct_count += 1
            
            st.info(f"結果: {correct_count}/{total_questions} 問正解")
            
            # 新しい問題を生成するためのガイド
            st.info("💡 新しい問題を生成するには、サイドバーの「問題生成」ボタンを押してください。")
    
    else:
        # 初期画面
        st.info("👈 サイドバーで設定を行い、「問題生成」ボタンを押して問題を生成してください。")
        
        # 使い方説明
        with st.expander("📋 使い方"):
            st.markdown("""
            1. **CSV名**: 英単語が含まれるCSVファイルを選択
            2. **文型**: 生成したい英文の文型を選択
            3. **問題数**: 1〜5問の範囲で選択
            4. **問題形式**: 記述形式または並び替えを選択
            5. **問題生成**: ボタンを押して問題を生成
            6. **解答**: 日本語訳を見て英文を入力
            7. **答え合わせ**: ボタンを押して正解を確認
            """)

if __name__ == "__main__":
    main()

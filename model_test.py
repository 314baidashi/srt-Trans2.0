import ollama
import time

def test_translation(model_name="7shi/llama-translate:8b-q4_K_M"):
    """测试翻译模型的功能"""
    print("开始测试翻译模型...")
    
    # 测试用例：20个日语句子
    test_cases = [
        "今日はとても良い天気ですね。",
        "新しいプロジェクトを始めることになりました。",
        "このレストランの料理は本当に美味しいです。",
        "来週の会議の準備を進めています。",
        "最近、新しい趣味を見つけました。",
        "この本はとても面白かったです。",
        "明日は友達と映画を見に行く予定です。",
        "新しいスマートフォンを買いました。",
        "毎日運動するようにしています。",
        "このアプリは使いやすいですね。",
        "来月から新しい仕事を始めます。",
        "週末は家族と過ごす予定です。",
        "この問題は複雑すぎます。",
        "新しい言語を勉強するのは楽しいです。",
        "この映画は感動的でした。",
        "来年の目標を考えています。",
        "このレシピは簡単に作れます。",
        "新しい友達ができました。",
        "このゲームは面白いですね。",
        "来週から旅行に行きます。"
    ]

    # 翻译结果存储
    results = []
    
    # 测试翻译
    for i, text in enumerate(test_cases, 1):
        print(f"\n测试用例 {i}/20:")
        print(f"原文: {text}")
        
        try:
            # 翻译成中文
            prompt = f"""### Instruction:
Translate Japanese to Mandarin.

### Input:
{text}

### Response:
"""
            messages = [{"role": "user", "content": prompt}]
            response = ollama.chat(model=model_name, messages=messages)
            chinese_trans = response["message"]["content"].strip()
            
            # 翻译成英文
            prompt = f"""### Instruction:
Translate Japanese to English.

### Input:
{text}

### Response:
"""
            messages = [{"role": "user", "content": prompt}]
            response = ollama.chat(model=model_name, messages=messages)
            english_trans = response["message"]["content"].strip()
            
            results.append({
                "original": text,
                "chinese": chinese_trans,
                "english": english_trans
            })
            
            print(f"中文翻译: {chinese_trans}")
            print(f"英文翻译: {english_trans}")
            
            # 添加短暂延迟，避免请求过快
            time.sleep(1)
            
        except Exception as e:
            print(f"翻译出错: {str(e)}")
            continue
    
    return results

def evaluate_translations(results):
    """评估翻译质量"""
    print("\n=== 翻译质量评估 ===")
    
    # 评估标准
    criteria = {
        "准确性": "翻译是否准确传达了原文的意思",
        "流畅性": "翻译是否自然流畅",
        "完整性": "是否完整翻译了所有内容"
    }
    
    # 评估结果
    evaluation = {
        "准确性": {"good": 0, "fair": 0, "poor": 0},
        "流畅性": {"good": 0, "fair": 0, "poor": 0},
        "完整性": {"good": 0, "fair": 0, "poor": 0}
    }
    
    # 评估每个翻译
    for result in results:
        print(f"\n原文: {result['original']}")
        print(f"中文: {result['chinese']}")
        print(f"英文: {result['english']}")
        
        # 这里可以添加更详细的评估逻辑
        # 目前使用简单的计数方式
        
        # 准确性评估
        if len(result['chinese']) > 0 and len(result['english']) > 0:
            evaluation["准确性"]["good"] += 1
        else:
            evaluation["准确性"]["poor"] += 1
            
        # 流畅性评估
        if "。" in result['chinese'] or "。" in result['english']:
            evaluation["流畅性"]["good"] += 1
        else:
            evaluation["流畅性"]["fair"] += 1
            
        # 完整性评估
        if len(result['chinese']) > len(result['original']) * 0.5 and \
           len(result['english']) > len(result['original']) * 0.5:
            evaluation["完整性"]["good"] += 1
        else:
            evaluation["完整性"]["fair"] += 1
    
    # 输出评估结果
    print("\n=== 评估结果 ===")
    for criterion, scores in evaluation.items():
        print(f"\n{criterion}:")
        print(f"优秀: {scores['good']}")
        print(f"一般: {scores['fair']}")
        print(f"较差: {scores['poor']}")

if __name__ == "__main__":
    print("=== 开始模型测试 ===")
    results = test_translation()
    evaluate_translations(results)
    print("\n=== 测试完成 ===")

import re

def split_with_parentheses(sarr, s):
  """
  寻找 s 中所有用小括号包含着 sarr_i 字符串的文字，将其与上文分开，并返回一个字符串列表。

  参数：
    sarr: 字符串数组
    s: 字符串

  返回：
    字符串列表
  """

  # 构造正则表达式，匹配用小括号包含的 sarr 中的字符串
  pattern = r"\((?:" + "|".join(sarr) + r")\)"

  # 使用正则表达式分割字符串
  splited = re.split(pattern, s)
  result = []

  result_index = 0

  # 将匹配到的括号内的字符串也添加到结果列表中
  for match in re.finditer(pattern, s):
    result += [splited[result_index], match.group()]
    result_index += 1

  return result

# 测试样例
sarr = ['hello', 'world']
s = 'hello, dude. (hello) this is next string (world) okay, good job (hello)'

result = split_with_parentheses(sarr, s)
print(result)
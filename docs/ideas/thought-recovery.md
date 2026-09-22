# Thought Recovery

## Ідея

Розширити LangSwitcher до відновлювача тексту з кількома мовами та помилковими розкладками всередині одного речення. Замість конвертації всього рядка система знаходить оптимальну послідовність точкових замін.

```text
ghbdsn, я вже зробив rjvsn але tests gflf.nm
↓
привіт, я вже зробив коміт але tests падають
```

## Типи сегментів

- `WRONG_LAYOUT`
- `INTENTIONAL_FOREIGN`
- `CODE`
- `URL`
- `PROPER_NAME`
- `AMBIGUOUS`

## Підхід

- Згенерувати для кожного span варіанти: залишити / EN→UK / UK→EN / PL-layer recovery.
- Оцінити послідовність словниками, character n-grams і переходами між мовами.
- Використати beam search по сегментаціях.
- Змінювати лише spans із достатнім margin між першим і другим кандидатом.
- Усе неоднозначне залишати або показувати в preview.

## UX

- Утримання хоткея показує reconstructed preview.
- 2–3 найкращі реконструкції для неоднозначного тексту.
- Undo навчає локальний словник користувача.
- Код, URL та навмисні іншомовні слова не змінюються.

## MVP

- EN/UK mixed sentences.
- Span-level decoding без LLM.
- Набір із реальних анонімізованих помилок.
- Метрики: character recovery accuracy, false replacement rate, undo rate.

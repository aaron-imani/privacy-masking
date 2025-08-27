from presidio_anonymizer import AnonymizerEngine, DeanonymizeEngine 
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer.entities import RecognizerResult, OperatorConfig

crypto_key = "WmZq4t7w!z%C&F)J"

anonymizer = AnonymizerEngine()
deanonymizer = DeanonymizeEngine()
analyzer = AnalyzerEngine()

original_text = 'My name is Mahmoud Moshirpour and my email is john.doe@example.com. I live in 3244 Main St., Mission Viejo. 542873775.'
print('Original:', original_text)

# print(analyzer.get_supported_entities())
results = analyzer.analyze(original_text, language='en')
print('Analyzer results:', results)

anonymized = anonymizer.anonymize(
    text=original_text,
    analyzer_results=results,
    operators={"DEFAULT": OperatorConfig("encrypt", {"key": crypto_key})}
)
print('Anonymized:', anonymized.text)

deanonymized = deanonymizer.deanonymize(
    text=anonymized.text,
    entities=anonymized.items,
    operators={"DEFAULT": OperatorConfig("decrypt", {"key": crypto_key})},
)
print('Deanonymized:', deanonymized.text)

assert deanonymized.text == original_text, "The deanonymized text does not match the original text."
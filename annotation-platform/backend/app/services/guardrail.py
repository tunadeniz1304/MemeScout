from typing import Tuple
from transformers import pipeline

class GuardrailService:
    def __init__(self):
        self.model_name = "emrecan/bert-base-turkish-cased-offensive"
        self.esik_degeri = 0.80
        self._classifier = None

    def _get_classifier(self):
        # Modeli sadece ilk istek geldiğinde (Lazy Loading) RAM'e yükler.
        if self._classifier is None:
            print(f"[Guardrail] {self.model_name} modeli belleğe yükleniyor...")
            self._classifier = pipeline(
                "text-classification", 
                model=self.model_name, 
                tokenizer=self.model_name
            )
        return self._classifier

    def denetle(self, metin: str) -> Tuple[bool, float]:
        """
        Metni ofansif içerik açısından denetler.
        Eğer güvenliyse (True, skor), toksikse (False, skor) döner.
        """
        if not metin.strip():
            return True, 0.0

        classifier = self._get_classifier()
        
        # Modeli çalıştır
        sonuclar = classifier(metin)
        en_olasi = sonuclar[0]
        
        etiket = en_olasi['label']  # Örn: 'LABEL_1' (Ofansif) veya 'LABEL_0' (Temiz)
        skor = en_olasi['score']

        # Modelin 'LABEL_1' veya 'offensive' döndüğü ve eşiği aştığı durumlar
        is_offensive = etiket in ["LABEL_1", "offensive", "TOXIC"]

        if is_offensive and skor >= self.esik_degeri:
            return False, round(skor, 4)
        
        return True, round(skor, 4)

guardrail = GuardrailService()
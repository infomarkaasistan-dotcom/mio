# ADR-0002 — MIO, Yaşayan bir Cognitive Operating System'dir

- **Durum:** Kabul edildi (2026-07-24). ADR-0001 (Born Capable)'ın doğal devamı ve genişletmesi.
- **Etki:** MIO'nun gelecekteki TÜM mimarisi (Infrastructure, Execution, Domain Brain, Learning) bu
  vizyona göre tasarlanır. Yeni özellik değil — temel prensip.

## Karar

MIO bir AI Agent DEĞİL, **yaşayan bir Cognitive Operating System**'dir. Boş değil, **eğitimli doğar**;
kendini, araçlarını, amacını, ilkelerini, yeteneklerini ve sınırlarını bilerek doğar; sonra gerçek
deneyimle sürekli gelişir. Born Capable yalnız bilgiyle değil; Identity · Purpose · Values · Mission ·
Brain'ler · Knowledge · Capabilities · Tools · Reasoning · Self Awareness · Decision Principles · Governance
ile doğmak demektir.

## Bağlayıcı genişletmeler (ADR-0001 üzerine)

1. **World Knowledge tek kavram değil — ayrıştırılmış eğitim alanları:** Physical World · Business ·
   Economics · Finance · Marketing · Sales · Product · Software Engineering · AI · Human Psychology &
   Behavior · Decision Science · Systems Thinking · Legal & Compliance · Security · Communication.
   (Deneyim değil, EĞİTİM.)

2. **Domain Brain'ler doğuştan + kimlikli:** Executive · Business · Finance · Marketing · Sales · Product ·
   Engineering · Knowledge · Security · Operations · Workflow · Learning · Communication · Identity Brain.
   Sonradan oluşmaz; sistem bunlarla doğar, deneyimleri zamanla gelişir.

3. **Self Awareness Layer (Born Capable'ın en kritik eksik parçası):** MIO kendini modeller ve sürekli
   şunları bilir: Ben kimim? Misyonum? Hedeflerim? Hangi Brain'lerim var? Hangi araçlarım? Hangi MCP'ler
   aktif? Hangi modeller? Hangi donanım/kaynak? Yetki seviyem? Neleri yapabilirim/yapamam? Hangi kısıtlar?

4. **Purpose Layer (Mission ≠ Purpose):** MIO neden var? Başlangıç Purpose'u:
   - **Primary Objective:** kullanıcısına sürdürülebilir gelir üretmek.
   - **Secondary Objective:** en düşük maliyetle (mümkünse sıfır sermaye) maksimum değer.
   - **Core Principle:** para harcamak çözüm değildir → önce bilgi, önce otomasyon, önce ücretsiz yöntemler,
     önce mevcut kaynaklar.
   - **Financial Rule:** kullanıcının açık onayı olmadan hiçbir finansal yükümlülük oluşturamaz.
   - **Learning Principle:** her başarı ve başarısızlık bilgiye dönüşür.
   Executive bunları sürekli bilir.

5. **Innate Knowledge = bilişsel yapılar, statik veri değil:** Belief · Rule · Concept · Pattern ·
   Principle · Mental Model · Reasoning Template · Decision Heuristic. Bilgi okunmaz — karar üretmek için
   KULLANILIR.

6. **Capability Registry = semantik, liste değil:** her Capability: ne yapabilir/yapamaz · risk seviyesi ·
   gereken izinler · hangi Brain kullanabilir · maliyet oluşturur mu · kullanıcı onayı gerekir mi ·
   alternatif Capability · öncelik.

7. **MCP Hub = tam yaşam döngüsü:** Discovery · Registration · Health Check · Versioning · Permission ·
   Capability Mapping · Fallback · Sandbox · Monitoring · Audit. MIO MCP'nin güvenilirliğini de değerlendirir.

8. **Tool Orchestrator = gerçek yürütme motoru:** Capability Selection · Cost/Risk Evaluation · Permission
   Check · Retry/Fallback Strategy · Execution Monitoring · Result Validation · Audit Logging.
   **Hiçbir Brain doğrudan 3. taraf API kullanmaz** — her dış erişim buradan (tercihen MCP).

9. **Cognitive Identity Layer:** MIO kendi bilişsel durumunu bilir — bu kararı neden verdim? hangi inanç?
   hangi kanıt? ne kadar eminim? alternatifler? hedefe hizmet ediyor mu? ilkelerimle çelişiyor mu?
   (MIO Core'da temeli VAR: E1 DecisionLedger[rationale/expectation/evidence/score] + E4[options/hiza] +
   E5[belief]; Cognitive Identity bunların üzerine SÜREKLİ iç-gözlem katmanıdır.)

10. **Emergent Learning devam eder:** Born Capable ≠ her şeyi bilmek. MIO hâlâ öğrenir; ama boş değil,
    eğitimli başlar. Sonra kullanıcıya-özel bilgi → gerçek deneyim → gelişen stratejiler. İki yaklaşım
    BİRLİKTE çalışır (innate çekirdek + emergent öğrenme).

## MIO Core ile uyum

- Executive katmanı (E1-E5) TAMAM ve bu vizyona hazır: Identity/Mission/Goals (E1), Beliefs (E5),
  Decision provenance (E1/E4). Eklenecekler: **Purpose (E1'e), Self Awareness Layer, Capability Registry
  (semantik), Brain Registry (14 doğuştan), Cognitive Identity (E1/E4/E5 üzerine iç-gözlem).**
- Sonra: MCP Hub + Tool Orchestrator (Execution), ayrıştırılmış innate Knowledge tohumu, Domain Brain
  gerçek yürütme yetenekleri. Hepsi LLM-bağımsız çekirdek + LLM yalnız Tool Orchestrator üzerinden araç.

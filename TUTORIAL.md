# 📖 Guia do Desenvolvedor: Automated Incident Post-Mortem & Root-Cause Synthesizer

Este projeto implementa um pipeline distribuído assíncrono e multi-modelo para automação de post-mortems pós-incidentes de produção.

---

## 🏛️ Arquitetura & Fluxo de Dados

1. **Webhook Ingestion (FastAPI):**
   A API recebe webhooks no formato `PagerDuty` com evento `incident.resolved` e responde com `202 Accepted` em tempo constante $O(1)$.

2. **Extração & Fragmentação (Redis + Celery):**
   O log bruto do incidente é armazenado no Redis e fracionado em blocos de 500 linhas. Um Celery Chord dispara execuções paralelas de filtragem.

3. **Roteamento Multi-Provider LLM:**
   - **DeepInfra (Llama 3 8B):** Executa o filtro de alta velocidade eliminando 95% de logs informativos/rotineiros.
   - **Ollama (Local):** Executa anonimização de PII (CPFs, e-mails, IPs internos, UUIDs).
   - **OpenAI (GPT-4o):** Consolida a linha do tempo limpa em um relatório final RCA estruturado em Markdown.

---

## 🧪 Execução dos Testes

Para rodar os testes unitários e de integração:

```bash
cd incident-postmortem-synthesizer
PYTHONPATH=. pytest tests/test_postmortem.py -v
```

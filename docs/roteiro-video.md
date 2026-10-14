# Roteiro do vídeo pitch (~5 min)

Grave a tela com o app rodando (`uvicorn app.main:app`), de preferência já com a chave do Gemini no `.env`, para aparecer "IA: Gemini" no topo.

| Tempo | O que mostrar | O que falar |
|---|---|---|
| 0:00-0:40 | Slide ou tela inicial | "O tutor esquece vacina e retorno, e a clínica perde o vínculo. Na sprint passada definimos uma IA generativa que transforma os dados do pet em cuidado personalizado. Agora ela está implementada." |
| 0:40-1:20 | Diagrama de arquitetura do README | "O app do tutor fala com uma API em FastAPI, que guarda tudo num banco SQLite. Antes de chamar a IA, regras de negócio calculam as pendências e a urgência. Depois montamos o prompt com os dados do pet e mandamos para o Google Gemini." |
| 1:20-2:20 | App do tutor → Rex → **Gerar lembrete** → abrir "Ver prompt" | "O Rex tem a antirrábica vencendo em 5 dias. Este é o prompt que vai para a IA, com espécie, idade, histórico e a pendência já classificada. E esta é a mensagem que ela devolve." |
| 2:20-3:00 | Mia → Gerar lembrete | "A Mia tem 12 anos, está com tudo atrasado e o tutor sumiu do app há 70 dias. A mesma IA muda o tom: é urgente, e ela chama o tutor de volta. Isso é personalização real, não um aviso genérico." |
| 3:00-3:50 | Chat: "Quais cuidados ele precisa nessa idade?" e depois "Ele comeu chocolate" | "O assistente responde usando o histórico do pet. E quando o tutor descreve uma emergência, uma regra de segurança responde na hora para procurar atendimento, sem depender da IA." |
| 3:50-4:30 | Thor → registrar a vacina (vencimento daqui a 1 ano) → pendência some. Depois Painel da clínica → Gerar lembretes de hoje | "Quando o tutor registra a vacina, a pendência some. Para a clínica, um clique gera os lembretes de todos os pacientes, e o mesmo endpoint é chamado todo dia às 8h por um fluxo no n8n." |
| 4:30-5:00 | Terminal com `pytest -v` passando + métricas | "Temos 17 testes automatizados, incluindo a integração com o Gemini e o fallback se a API cair. Resultado: o tutor recebe um aviso que faz sentido, e a clínica ganha retorno recorrente." |

Dica: antes de gravar, rode `python -m app.database` para zerar o banco e deixar o histórico limpo.

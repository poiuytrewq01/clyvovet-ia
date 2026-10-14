# Componente de Inteligência Artificial - CLYVO VET (definição - Sprint 3)

> Documento da entrega anterior, mantido como referência. A implementação desta definição está no restante do repositório (ver README).

## Qual problema a IA resolve

Hoje o tutor esquece vacina, esquece retorno, não sabe direito o que fazer com o pet em cada fase da vida. A IA entra pra resolver isso: ler os dados do pet (espécie, idade, histórico) e gerar uma mensagem personalizada de cuidado, em vez de um lembrete genérico igual pra todo mundo.

Exemplo: em vez de mandar "vacina pendente" pra todo mundo igual, a IA gera algo tipo "Rex, cachorro de 2 anos, está com a vacina antirrábica vencendo em 5 dias. Agende o reforço com a clínica."

## Abordagem escolhida: IA Generativa via API

LLM acessado por API pronta (Google Gemini). Não há treinamento de modelo do zero: os dados do pet são enviados ao modelo, que gera a mensagem.

Por que essa abordagem: é a mais viável pro projeto (não precisa de base de dados gigante nem de treino), é a que mais conversa com o tema da disciplina (Generative IA) e é fácil de demonstrar: dado do pet entra, mensagem sai pronta.

1. O sistema pega os dados do pet salvos (espécie, idade, histórico de vacina e consulta).
2. Monta um prompt com esses dados.
3. Manda o prompt pra API do LLM.
4. O LLM devolve o texto pronto.
5. O app mostra a mensagem pro tutor.

O mesmo mecanismo alimenta o assistente dentro do app: o tutor pergunta, o sistema manda a pergunta junto com os dados do pet pro LLM, e ele responde.

## Dados que a IA usa

- Espécie, raça e idade do pet (cadastro) - personaliza a mensagem por fase de vida.
- Histórico de vacinas - identifica o que está pendente ou vencendo.
- Consultas e medicamentos - dão contexto para a mensagem.
- Check-ins do tutor (gamificação) - indicam se o tutor está engajado ou sumiu.

## Benefícios

- Tutor: aviso que faz sentido pra situação real do pet dele.
- Clínica: menos gente esquecendo de voltar, mais consultas preventivas recorrentes.

## Regra de urgência (plus)

Regra simples no código para decidir a urgência antes do LLM: vacina vencida há mais de 30 dias é urgente, vencendo em 5 dias é normal. **Implementada na Sprint 4** (`app/urgencia.py`).

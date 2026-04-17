# 🤖 Bot Telegram — Gestão de Serviços

Bot completo para consulta da planilha de serviços via Telegram.
Lê os dados direto do **CSV público** do Google Sheets — sem necessidade de API Key ou credenciais.

---

## 📁 Arquivos

```
bot/
├── bot.py           # Lógica principal do bot
├── sheets.py        # Leitura e análise da planilha
├── requirements.txt # Dependências
└── .env.example     # Variáveis de ambiente
```

---

## 🚀 Configuração

### 1. Verificar que a planilha está publicada como CSV

A URL do CSV já está configurada em `sheets.py`. Se precisar trocar:
1. Google Sheets → Arquivo → Compartilhar → Publicar na web
2. Selecione a aba → formato **CSV** → Publicar
3. Copie o link e atualize `CSV_URL` em `sheets.py`

### 2. Criar o bot no Telegram

1. Converse com [@BotFather](https://t.me/BotFather)
2. `/newbot` → siga as instruções
3. Copie o **token**

### 3. Configurar e rodar

```bash
# Instalar dependências
pip install -r requirements.txt

# Definir token e rodar
export TELEGRAM_BOT_TOKEN="seu_token_aqui"
python bot.py
```

Windows (PowerShell):
```powershell
$env:TELEGRAM_BOT_TOKEN="seu_token_aqui"
python bot.py
```

---

## 💬 Comandos disponíveis

### 📊 Resumos
| Comando | Descrição |
|---|---|
| `/hoje` | Resumo do dia: total, faturamento, procurações, pendentes |
| `/mes` | Resumo do mês atual |
| `/semana` | Resumo dos últimos 7 dias |

### 📝 Procurações
| Comando | Descrição |
|---|---|
| `/procuracoes` | Lista todas as procurações de hoje |
| `/pendentes` | Procurações sem status OK hoje |
| `/pendentes_mes` | Procurações pendentes no mês inteiro |

### 🏆 Rankings
| Comando | Descrição |
|---|---|
| `/ranking` | Top lojas do mês (por volume) |
| `/operadores` | Top operadores do mês |

### 🎬 Vídeos
| Comando | Descrição |
|---|---|
| `/videos` | Vídeos sem status OK hoje |

### 💰 Financeiro
| Comando | Descrição |
|---|---|
| `/faturamento` | Faturamento por loja no mês |
| `/grupos` | Resumo por grupo (qtd + faturamento + líquido) |
| `/pagamentos` | Distribuição por forma de pagamento |

### 🗂️ Serviços
| Comando | Descrição |
|---|---|
| `/servicos` | Contagem por tipo de serviço no mês |

### 🔍 Busca
| Comando | Descrição |
|---|---|
| `/buscar João` | Busca por nome do cliente |
| `/buscar IQL1A55` | Busca por placa |

### ⚙️ Utilitários
| Comando | Descrição |
|---|---|
| `/atualizar` | Força buscar dados novos da planilha |

---

## 💡 Linguagem natural

O bot também entende mensagens como:
- "como foi hoje"
- "procurações pendentes"
- "ranking de lojas"
- "faturamento do mês"
- "vídeos faltando"

---

## ☁️ Deploy gratuito (Railway)

1. Crie conta em [railway.app](https://railway.app)
2. Novo projeto → Deploy from GitHub (suba os arquivos)
3. Variables → adicione `TELEGRAM_BOT_TOKEN`
4. O bot roda 24/7 automaticamente

---

## 🔄 Cache

Os dados ficam em cache por **5 minutos** para não sobrecarregar o Google Sheets.
Use `/atualizar` para forçar a leitura imediata.

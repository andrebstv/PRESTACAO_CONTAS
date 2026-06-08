# Relatório de Processamento de Extratos - AVLAC [ATUALIZADO]

Este documento resume o trabalho realizado para ler, processar e categorizar automaticamente os extratos bancários da **Associação de Voo Livre de Alfredo Chaves (AVLAC)** referente aos anos de 2025 e 1º semestre de 2026.

---

## 🛠️ O que foi feito

1. **Desenvolvimento do Script de Parsing**:
   * Foi criado o script [processar_extrato.py](file:///media/hdfs/Offlabel/SincFolder/Pessoais/VooLivre/07%20-%20AVLAC/01%20-%20Prestacao%20de%20Contas/01%20-%202025%20a%201sem%202026/processar_extrato.py).
   * Ele remove cabeçalhos repetidos de página, quebras de página (`\x0c`) e consolida transações multilinhas do Sicoob (capturando pagador/recebedor, CPFs mascarados e observações do Pix na última linha).

2. **Categorização Automática Atualizada**:
   * As regras foram ajustadas de acordo com as suas instruções:
     * Recebimentos de CNPJs de empresas (como *Castelhanos Beach & Bike*) foram classificados como **"Entrada sem classificação"**.
     * Pagamentos/Transferências para o CPF de Frederico Randow foram categorizados como **"Reembolso despesas/Eventos"** (preservando o comentário do Pix, caso exista).
     * **NOVA REGRA**: Recebimentos na faixa de **R$ 30,00 a R$ 100,00** foram classificados como **"Inscrição Evento (XC AVLAC)"**.
     * **NOVA REGRA**: Recebimentos **acima de R$ 100,00** foram classificados como **"Anuidade"**.
     * Demais despesas (troféus, camisas, confraternização), tarifas, internet e manutenção da estação meteorológica foram aplicadas com sucesso.

3. **Agrupamento e Interatividade**:
   * **Agrupamento por Ano**: As transações são separadas por ano (ex: 2025 e 2026).
   * **Visualização no Markdown**: O arquivo Markdown agora usa elementos `<details>` para esconder/mostrar as transações por categoria. Você pode clicar no título de qualquer categoria no próprio leitor de markdown (no VS Code, GitHub, etc.) para abrir e fechar a tabela correspondente.
   * **Dashboard HTML Interativo**: Foi gerado um arquivo HTML autônomo de alta qualidade para apresentação. Ele possui busca em tempo real, seleção de anos por abas, filtros por categoria e linhas expansíveis para visualizar os comentários Pix de cada transação.
   * **Saldos Inicial e Final (NOVO)**: O script agora varre o extrato procurando o histórico de saldos. Ele calcula e exibe automaticamente o **Saldo Anterior / Inicial** e o **Saldo Final**, tanto nos relatórios Markdown quanto no Dashboard HTML (no card de saldo do dashboard, ao alternar entre os anos, os saldos inicial e final são recalculados dinamicamente para o ano selecionado).

4. **Arquivos Gerados na Pasta**:
   * **Planilha para Excel**: [AVLAC-012025_merged_processado.csv](file:///media/hdfs/Offlabel/SincFolder/Pessoais/VooLivre/07%20-%20AVLAC/01%20-%20Prestacao%20de%20Contas/01%20-%202025%20a%201sem%202026/AVLAC-012025_merged_processado.csv)
   * **Relatório Dinâmico Markdown**: [AVLAC-012025_merged_relatorio.md](file:///media/hdfs/Offlabel/SincFolder/Pessoais/VooLivre/07%20-%20AVLAC/01%20-%20Prestacao%20de%20Contas/01%20-%202025%20a%201sem%202026/AVLAC-012025_merged_relatorio.md) (com colapso de tabelas e saldos anterior/final por ano)
   * **Dashboard Interativo Premium**: [AVLAC-012025_merged_dashboard.html](file:///media/hdfs/Offlabel/SincFolder/Pessoais/VooLivre/07%20-%20AVLAC/01%20-%20Prestacao%20de%20Contas/01%20-%202025%20a%201sem%202026/AVLAC-012025_merged_dashboard.html)

---

## 📊 Resumo Financeiro Consolidado (Todos os Anos)

O extrato consolidou **181 transações** no período. Abaixo está o resumo gerado:

| Tipo | Métrica | Valor |
| :--- | :--- | :--- |
| 🏦 | **Saldo Anterior Geral (31/12/2024)** | **R$ 9.284,75** |
| 🟢 | **Total de Receitas (Créditos)** | **R$ 17.156,53** |
| 🔴 | **Total de Despesas (Débitos)** | **R$ 16.727,20** |
| ⚖️ | **Saldo Líquido no Período** | **R$ 429,33** |
| 🏁 | **Saldo Final Geral (Consolidado)** | **R$ 9.714,08** |

### 🟢 Detalhamento de Receitas por Categoria (Todos os Anos)

| Categoria | Qtd. Transações | Total (R$) |
| :--- | :---: | :---: |
| **Anuidade** | 72 | R$ 12.180,00 |
| **Inscrição Evento (XC AVLAC)** | 50 | R$ 3.080,00 |
| **Rendimento de Capital** | 1 | R$ 202,95 |
| **Devolução / Estorno** | 2 | R$ 933,58 |
| **Entrada sem classificação** | 6 | R$ 760,00 |

### 🔴 Detalhamento de Despesas por Categoria (Todos os Anos)

| Categoria | Qtd. Transações | Total (R$) |
| :--- | :---: | :---: |
| **Despesa Evento (Confraternização / Troféus / Camisas)** | 11 | R$ 7.979,00 |
| **Reembolso despesas/Eventos** | 5 | R$ 4.276,91 |
| **Manutenção da Estação / Rampa** | 2 | R$ 1.266,11 |
| **Tarifas Bancárias** | 17 | R$ 549,53 |
| **Internet Estação** | 5 | R$ 520,35 |
| **Serviços Prestados / Limpeza** | 2 | R$ 450,00 |
| **Devolução Pix Enviada** | 2 | R$ 400,00 |
| **Despesa a Categorizar / Outras** | 6 | R$ 1.285,30 |

---

## 💡 Como usar o script no futuro

Se você tiver novos arquivos de extrato TXT (por exemplo, no segundo semestre de 2026):
1. Coloque o arquivo TXT na pasta `txt/`.
2. Abra um terminal na pasta onde o script está e execute:
   ```bash
   python3 processar_extrato.py
   ```
3. O script lerá automaticamente o arquivo `.txt` da pasta, gerará um novo arquivo `.csv` e um novo relatório `.md` na mesma pasta do script com as categorias aplicadas.

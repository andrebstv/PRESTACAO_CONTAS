# Plano de Implementação - Processamento de Extratos AVLAC [APROVADO]

Este plano descreve o desenvolvimento de um algoritmo em Python para processar os extratos bancários em formato TXT da **Associação de Voo Livre de Alfredo Chaves (AVLAC)**. O objetivo é extrair as transações, categorizar automaticamente os recebimentos (como anuidades e inscrições de eventos) e despesas (como taxas, internet, troféus e eventos) e exportar tudo em um formato CSV pronto para importação no Excel.

---

## Regras de Categorização Alinhadas e Aprovadas

Com base no feedback do usuário, as regras de categorização automática das transações serão estruturadas da seguinte forma:

### Recebimentos (Créditos / C)
1. **Inscrição Evento (XC AVLAC)**:
   * **Critério**:
     * Transações com descrição contendo termos como `"XC AVLAC"`, `"XC AVILAC"`, `"XCAvlac"`, `"inscricao"` ou `"inscrição"`.
     * **NOVA REGRA**: Qualquer recebimento de pessoa física (CPF) cuja faixa de valor esteja **entre R$ 30,00 e R$ 100,00** (inclusive).
2. **Rendimento de Capital (Juros S/Capital)**:
   * **Critério**: Descrição `"CRÉD.JUROS S/CAPITAL"`.
3. **Devolução / Estorno**:
   * **Critério**: Descrição `"ESTORNO PIX EMITIDO"` ou `"CRÉDITO DEVOLUÇÃO PIX"`.
4. **Anuidade**:
   * **Critério**:
     * Qualquer outro recebimento por Pix/Transferência que seja de um valor **acima de R$ 100,00** vindo de um **CPF de pessoa física** (não CNPJ) ou contendo `"Anuidade"` no comentário.
5. **Entrada sem classificação**:
   * **Critério**: Recebimentos que venham de empresas (CNPJs) que não se enquadram nas regras acima (ex: *Castelhanos Beach & Bike*) ou créditos que não correspondam a anuidades típicas ou inscrições de eventos.
6. **Outras Receitas**:
   * **Critério**: Outros créditos diversos abaixo de R$ 30,00.

### Despesas (Débitos / D)
1. **Tarifas Bancárias**:
   * **Critério**: Descrição contendo `"DÉBITO PACOTE SERVIÇOS"` ou `"DÉB.TÍTULO COBRANÇA"` (se não for outro convênio).
2. **Reembolso despesas/Eventos**:
   * **Critério**: Pagamentos/Transferências para **Frederico Aguirre von Randow** (CPF/chave contendo `***.801.627-**`). O script deve incluir o comentário do Pix no campo correspondente, caso exista.
3. **Internet Estação**:
   * **Critério**: Destinatário contendo `"SCHERRERNET TELECOMUNICACOES"`. (Parceiro de internet da rampa/estação).
4. **Manutenção da Estação / Rampa**:
   * **Critério**: Descrição contendo `"estacao metereologica"` ou `"mastro estacao"`, ou pagamento à **SOL SPORTS** (CNPJ `85.255.743/0001-65` - Sol Paragliders, tipicamente birutas/equipamentos).
5. **Despesa Evento (Confraternização / Troféus / Camisas)**:
   * **Critério**:
     * Descrição contendo `"repasse festa"`, `"churrasqueiro"`, `"Feijao Tropeiro"`, `"cerveja e carvao"`, `"cache da banda"`, `"Bar do Bruxo"`.
     * Pagamentos para a **Casa do Acrílico Ltda** (CNPJ `40.612.231/0001-70` - Troféus do evento).
     * Pagamentos para **Mar Azul Confecções** (CNPJ `48.024.083/0001-85` - Camisetas do evento) ou **Tom & Cor / Brandini** (CNPJ `36.320.364/0001-04` - Estamparia de uniformes/camisetas).
6. **Serviços Prestados / Limpeza**:
   * **Critério**: Pagamentos para **Lucinete Siqueira dos Santos** (provável responsável pela limpeza da rampa ou serviços gerais).
7. **Devolução Pix Enviada**:
   * **Critério**: Descrição `"DÉBITO DEVOLUÇÃO PIX"`.
8. **Despesa a Categorizar / Outras**:
   * **Critério**: Qualquer outro débito que não se enquadre nos critérios anteriores.

---

## Alterações Propostas

### [Algoritmo de Processamento]

#### [NEW] [processar_extrato.py](file:///media/hdfs/Offlabel/SincFolder/Pessoais/VooLivre/07%20-%20AVLAC/01%20-%20Prestacao%20de%20Contas/01%20-%202025%20a%201sem%202026/processar_extrato.py)
* Novo script Python que fará:
  1. Varredura da pasta `txt` para localizar arquivos de extrato (como `AVLAC-012025_merged.txt`).
  2. Limpeza dos caracteres especiais (como quebras de página `\x0c`).
  3. Parsing robusto de blocos multilinhas de transações (agrupando data, documento, descrição, valor e detalhes do favorecido/comentário Pix).
  4. Categorização automática baseada em regras regex flexíveis e faixas de valores.
  5. Exportação para um CSV codificado em `utf-8-sig` (ideal para abrir diretamente no Excel em português sem corromper acentos).
  6. Geração de um arquivo Markdown de relatório financeiro com totais por categoria.
  7. Exibição de um resumo financeiro formatado no terminal com totais por categoria.

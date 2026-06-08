# 📊 AVLAC - Prestação de Contas Automatizada

Este repositório contém um sistema em Python para processar os extratos bancários em formato TXT (padrão Sicoob) da **Associação de Voo Livre de Alfredo Chaves (AVLAC)**, categorizar as movimentações financeiras de forma automática e gerar relatórios interativos.

O sistema foi estruturado para ser **totalmente automatizado**. Ao atualizar o arquivo de extrato no repositório, os relatórios e o dashboard de apresentação na web atualizam-se sozinhos.

---

## 🚀 Como usar este template (Fork e Pages)

Se você deseja reutilizar este projeto para outra prestação de contas ou criar um novo site:

1. **Faça um Fork** deste repositório para a sua conta do GitHub.
2. **Substitua o arquivo TXT** de extrato original dentro da pasta `txt/` pelo seu novo arquivo de extrato.
3. **Faça o Commit e Push** das alterações para a branch `main`.
4. **Ative o GitHub Pages**:
   * No seu repositório no GitHub, vá em **Settings** (Configurações) > **Pages**.
   * Em *Build and deployment* > *Source*, selecione **GitHub Actions** (em vez de *Deploy from a branch*).
5. Pronto! A partir de agora, toda vez que você alterar o arquivo TXT, o GitHub Actions irá:
   * Processar o novo extrato.
   * Atualizar os relatórios e a planilha CSV automaticamente.
   * Publicar o novo Dashboard interativo no seu link público do GitHub Pages.

---

## 🛠️ Execução Local

Caso prefira rodar o algoritmo localmente no seu computador:

1. Certifique-se de ter o Python 3 instalado.
2. Coloque seu arquivo de extrato em formato `.txt` dentro da pasta `txt/`.
3. Abra um terminal na pasta do projeto e execute:
   ```bash
   python3 processar_extrato.py
   ```
4. O script gerará na raiz da pasta:
   * **`index.html`**: O Dashboard financeiro interativo (abra dando dois cliques para ver no navegador).
   * **`relatorio.md`**: Relatório financeiro formatado em Markdown com tabelas expansíveis.
   * **`extrato_processado.csv`**: Planilha com as transações limpas e categorizadas, pronta para o Excel.

---

## 📊 Regras de Categorização Aplicadas

### 🟢 Recebimentos (Créditos)
* **Inscrição Evento (XC AVLAC)**: Recebimentos Pix/Transferências identificados com comentários de evento (ex: "XC AVLAC") ou qualquer Pix de pessoa física no valor de **R$ 30,00 a R$ 100,00**.
* **Anuidade**: Recebimentos Pix de pessoa física com valor **acima de R$ 100,00** ou contendo "Anuidade" no comentário.
* **Rendimento de Capital**: Dividendos e juros sobre capital próprio do banco Sicoob.
* **Devolução / Estorno**: Estornos de pagamentos anteriores.
* **Entrada sem classificação**: Recebimentos vindos de CNPJs de empresas (ex: patrocínios) ou valores atípicos.

### 🔴 Saídas (Despesas)
* **Reembolso despesas/Eventos**: Transferências destinadas a diretores da associação (Frederico Randow) para cobertura de despesas.
* **Tarifas Bancárias**: Débitos automáticos de pacotes de serviços bancários.
* **Internet Estação**: Mensalidades de conexão da estação meteorológica (provedor Scherrernet).
* **Manutenção da Estação / Rampa**: Custos com mastros, cimento, equipamentos de rampa e pagamentos à Sol Sports (birutas).
* **Despesa Evento (Confraternização / Troféus / Camisas)**: Pagamentos para troféus (Casa do Acrílico), camisas de eventos (Mar Azul / Tom & Cor), churrasqueiros, tropeiro, cerveja e banda.
* **Serviços Prestados / Limpeza**: Custos de conservação e limpeza da rampa (Lucinete Siqueira).
* **Devolução Pix Enviada**: Devolução de Pix recebidos indevidamente.
* **Despesa a Categorizar / Outras**: Despesas gerais sem identificação clara de finalidade.

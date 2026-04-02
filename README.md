# Portal de Degustações — Supren Veg

Portal estático hospedado no GitHub Pages com os formulários e cards de degustação da Supren Veg.

URL pública: `https://supren-veg.github.io/degustacoes-supren`

## Estrutura

| Arquivo | Descrição |
|---------|-----------|
| `portal.html` | Portal principal com cards de degustação |
| `dashboard.html` | Dashboard resumido |
| `form1_agendamento.html` | Formulário de agendamento (vendedor) |
| `form2_kit_briefing.html` | Briefing do kit (responsável) |
| `form3a_vendedor.html` | Avaliação pós-evento (vendedor) |
| `form3b_degustador.html` | Avaliação pós-evento (degustador) |
| `form4_devolucao.html` | Devolução do kit (responsável) |
| `form5_relatorio.html` | Relatório final (gerado automaticamente) |
| `dados.js` | Dados sincronizados do Supabase (gerado por script) |
| `sincronizar_portal.py` | Script Python para sincronizar dados do Supabase |
| `sincronizar_automatico.bat` | Executa o script de sincronização no Windows |

## Como sincronizar os dados

```bash
python sincronizar_portal.py
```

Ou executar `sincronizar_automatico.bat` no Windows.

O script lê as degustações do Supabase e regenera `dados.js`.

## Portal — Funcionamento dos cards

Cada card de degustação exibe:
- Status, cliente, data, kit, degustador
- Botões de formulário com o **primeiro nome do responsável** (ex: "Ygor", "Ana")
- Link **Relatório Final** — aparece **apenas** quando `status === "Finalizado"`

## Relatório Final

O link do Relatório Final é gerado automaticamente a partir dos dados da degustação (sem preenchimento manual). Ele só fica visível no portal após o status ser marcado como **Finalizado** no sistema de gestão (`gestao-supren`).

Para finalizar uma degustação: acesse o gestão Supren → Degustações → clique em **Gerar Relatório Final** no card correspondente.

## Sincronização com Notion

O script `sincronizar_portal.py` consulta o Supabase (tabela `public.degustacoes`) que é alimentada pelo Notion via automação.

## Deploy

Push na branch `main` publica automaticamente no GitHub Pages.

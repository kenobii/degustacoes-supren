// Supren Veg — helper de envio de formulários para a API do gestao-supren
// Gerado automaticamente por sincronizar_portal.py — NÃO EDITE MANUALMENTE

(function () {
  'use strict';

  function getIdFromUrl() {
    return new URLSearchParams(window.location.search).get('id') || null;
  }

  function formDataToObject(formData) {
    const obj = {};
    const keys = new Set(formData.keys());
    for (const key of keys) {
      const values = formData.getAll(key);
      obj[key] = values.length === 1 ? values[0] : values;
    }
    return obj;
  }

  /**
   * Coleta os dados do formulário, salva no localStorage como fallback
   * e envia para a API do gestao-supren.
   *
   * @param {number} formNumero  1=Agendamento 2=Kit 3=Vendedor 4=Degustador 5=Devolução 6=Relatório
   * @param {FormData} formData  Resultado de new FormData(formElement)
   */
  window.submitToApi = async function (formNumero, formData) {
    const id = getIdFromUrl();
    const data = formDataToObject(formData);
    data.savedAt = new Date().toISOString();

    // Fallback local
    if (id) {
      try {
        localStorage.setItem('form' + formNumero + '_' + id, JSON.stringify(data));
      } catch (_) {}
    }

    // Envio para a API
    if (id && window.FORMS_API_BASE && window.FORMS_API_KEY) {
      try {
        await fetch(
          window.FORMS_API_BASE + '/api/forms/' + id + '/' + formNumero,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': 'Bearer ' + window.FORMS_API_KEY,
            },
            body: JSON.stringify(data),
          }
        );
      } catch (_) {
        // falha silenciosa — dado já está no localStorage
      }
    }
  };
})();

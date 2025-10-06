// static/js/data_upload.js
document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('upload-form');
  const status = document.getElementById('status');
  const previewArea = document.getElementById('preview-area');
  const previewTable = document.getElementById('preview-table');
  const btnCommit = document.getElementById('btn-commit');
  const toggleEdit = document.getElementById('toggle-edit');

  let previewJSON = null;
  let editMode = false;

  function escapeHtml(unsafe) {
    if (unsafe === null || unsafe === undefined) return '';
    return String(unsafe).replace(/[&<>"'`=\/]/g, function (s) {
      return ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
        '/': '&#x2F;',
        '`': '&#x60;',
        '=': '&#x3D;'
      })[s];
    });
  }

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const fileInput = document.getElementById('file');
    if (!fileInput.files.length) {
      alert('Please choose a file to upload');
      return;
    }
    const fd = new FormData();
    fd.append('file', fileInput.files[0]);
    fd.append('exam_type', document.getElementById('exam_type').value);
    fd.append('semester', document.getElementById('semester').value);
    fd.append('year', document.getElementById('year').value);
    fd.append('file_label', document.getElementById('file_label').value);

    status.textContent = 'Parsing file...';
    fetch('/api/uploads/preview', { method: 'POST', body: fd })
      .then(r => r.json())
      .then(data => {
        if (data.error) {
          status.textContent = 'Error: ' + data.error;
          return;
        }
        previewJSON = data;
        status.textContent = data.status_message || 'Preview ready';
        renderPreview(data);
        previewArea.style.display = 'block';
      }).catch(err => {
        status.textContent = 'Preview failed: ' + err;
      });
  });

  function formatPartsWithAB(partsArr) {
    // partsArr is array of strings or numbers or null; return HTML string
    return partsArr.map(p => {
      if (p === null || p === undefined || p === '' ) {
        return '<span style="color:red;font-weight:700;">AB</span>';
      }
      const s = String(p);
      if (s.toUpperCase() === 'AB' || s.toUpperCase() === 'ABS' || s.toUpperCase() === 'ABSENT') {
        return '<span style="color:red;font-weight:700;">AB</span>';
      }
      return escapeHtml(s);
    }).join('/');
  }

  function renderPreview(data) {
    previewTable.innerHTML = '';
    const rows = data.preview_rows || [];
    const subjectCols = data.subject_cols || [];
    const metaCols = data.meta_cols || [];

    const table = document.createElement('table');
    table.className = 'table';
    table.style.width = '100%';
    table.style.borderCollapse = 'collapse';

    const thead = document.createElement('thead');
    const headRow = document.createElement('tr');
    ['PIN','Name','Attendance'].forEach(h => {
      const th = document.createElement('th'); th.textContent = h; th.style.padding='8px'; th.style.border='1px solid #eee'; headRow.appendChild(th);
    });

    subjectCols.forEach(sc => {
      const th = document.createElement('th');
      let subName = null;
      for (let r of rows) {
        for (let s of r.subjects) {
          if (s.sub_code === sc && s.sub_name) { subName = s.sub_name; break; }
        }
        if (subName) break;
      }
      if (subName) {
        th.innerHTML = `${escapeHtml(subName)} <br><small>(${escapeHtml(sc)})</small>`;
      } else {
        th.innerHTML = `Unknown subject <br><small>(${escapeHtml(sc)})</small>`;
      }
      th.style.padding='8px'; th.style.border='1px solid #eee';
      headRow.appendChild(th);
    });

    metaCols.forEach(mc => {
      const th = document.createElement('th'); th.textContent = mc; th.style.padding='8px'; th.style.border='1px solid #eee'; headRow.appendChild(th);
    });

    ['Errors','Actions'].forEach(h => {
      const th = document.createElement('th'); th.textContent = h; th.style.padding='8px'; th.style.border='1px solid #eee'; headRow.appendChild(th);
    });

    thead.appendChild(headRow);
    table.appendChild(thead);

    const tbody = document.createElement('tbody');
    rows.forEach((r, rowIndex) => {
      const tr = document.createElement('tr');
      tr.style.border='1px solid #f1f1f1';

      const tdPin = document.createElement('td'); tdPin.textContent = r.pin || ''; tdPin.style.padding='8px'; tr.appendChild(tdPin);
      const tdName = document.createElement('td'); tdName.textContent = r.name || ''; tdName.style.padding='8px'; tr.appendChild(tdName);
      const tdAtt = document.createElement('td'); tdAtt.textContent = (r.attendance!=null) ? r.attendance : ''; tdAtt.style.padding='8px'; tr.appendChild(tdAtt);

      subjectCols.forEach(sc => {
        const td = document.createElement('td'); td.style.padding='8px'; td.style.border='1px solid #eee';
        const subj = r.subjects.find(s => s.sub_code === sc);
        if (!subj) {
          td.textContent = '';
        } else {
          if (subj.error) {
            td.innerHTML = `<span style="color:red">${escapeHtml(subj.display || subj.error)}</span>`;
          } else {
            // prefer parsed_components display where available
            if (subj.parsed_components) {
              const pc = subj.parsed_components;
              const parts = [
                pc.mid1 === null || pc.mid1 === undefined ? null : pc.mid1,
                pc.mid2 === null || pc.mid2 === undefined ? null : pc.mid2,
                pc.internal === null || pc.internal === undefined ? null : pc.internal,
                pc.end_sem === null || pc.end_sem === undefined ? null : pc.end_sem
              ];
              td.innerHTML = formatPartsWithAB(parts);
            } else if (subj.display) {
              // subj.display may be "AB" or "18/AB/14/AB" or "A+"
              // if display contains slashes, split and highlight AB parts
              if (String(subj.display).indexOf('/') !== -1) {
                const parts = String(subj.display).split('/').map(p => (p === null || p === undefined || p.trim() === '') ? null : p.trim());
                td.innerHTML = formatPartsWithAB(parts);
              } else {
                // display single token
                if (String(subj.display).toUpperCase() === 'AB' || String(subj.display).toUpperCase() === 'ABS' || String(subj.display).toUpperCase() === 'ABSENT') {
                  td.innerHTML = '<span style="color:red;font-weight:700;">AB</span>';
                } else {
                  td.textContent = subj.display;
                }
              }
            } else if (subj.raw_mark != null) {
              td.textContent = subj.raw_mark;
            } else {
              td.textContent = '';
            }

            // add small meta about score/flags
            if (subj.subject_score !== undefined && subj.subject_score !== null) {
              const metaDiv = document.createElement('div');
              metaDiv.style.fontSize = '11px';
              metaDiv.style.color = '#666';
              metaDiv.style.marginTop = '4px';
              metaDiv.textContent = `Score: ${subj.subject_score} | mid_fail:${subj.mid_fail} | backlog:${subj.backlog}`;
              td.appendChild(metaDiv);
            }
          }
        }
        tr.appendChild(td);
      });

      metaCols.forEach(mc => {
        const td = document.createElement('td'); td.style.padding='8px'; td.style.border='1px solid #eee';
        if (r.meta && (mc in r.meta)) {
          td.textContent = r.meta[mc] || '';
        } else {
          td.textContent = '';
        }
        tr.appendChild(td);
      });

      const tdErr = document.createElement('td'); tdErr.style.padding='8px';
      if (r.row_errors && r.row_errors.length) {
        r.row_errors.forEach(m => {
          const d = document.createElement('div'); d.style.color='red'; d.textContent = '⚠ ' + m; tdErr.appendChild(d);
        });
      }
      tr.appendChild(tdErr);

      const tdAct = document.createElement('td'); tdAct.style.padding='8px';
      const hasConflict = r.subjects.some(s => s.duplicate_status === 'conflict');
      if (hasConflict) {
        const sel = document.createElement('select');
        sel.innerHTML = `<option value="overwrite">Overwrite</option><option value="keep_old">Keep Old</option><option value="skip">Skip</option>`;
        tdAct.appendChild(sel);
        const note = document.createElement('div'); note.style.fontSize='12px'; note.textContent='(applies to all conflicting subjects in row)';
        tdAct.appendChild(note);
      } else {
        tdAct.textContent = '-';
      }
      tr.appendChild(tdAct);

      tbody.appendChild(tr);
    });

    table.appendChild(tbody);
    previewTable.appendChild(table);
  }

  toggleEdit.addEventListener('click', () => {
    editMode = !editMode;
    toggleEdit.textContent = editMode ? 'Exit Edit' : 'Edit';
    document.querySelectorAll('#preview-table td').forEach(td => {
      td.contentEditable = editMode ? 'true' : 'false';
    });
  });

  btnCommit.addEventListener('click', () => {
    if (!previewJSON) {
      alert('No preview to commit');
      return;
    }
    const payload = {
      file_label: previewJSON.file_label,
      exam_type: previewJSON.exam_type,
      semester: previewJSON.semester,
      year: previewJSON.class_year || previewJSON.year || 0,
      rows: previewJSON.preview_rows.map(r => ({
        pin: r.pin,
        name: r.name,
        attendance: r.attendance,
        subjects: r.subjects.map(s => ({
          sub_code: s.sub_code,
          raw_mark: s.raw_mark,
          absent: s.absent,
          parsed_components: s.parsed_components || null,
          action: s.duplicate_status === 'conflict' ? 'overwrite' : 'overwrite'
        })),
      }))
    };

    fetch('/api/uploads/commit', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    }).then(r => r.json()).then(data => {
      if (data.error) {
        alert('Commit failed: ' + data.error);
      } else {
        alert('Committed ' + data.committed + ' records.');
        location.reload();
      }
    }).catch(err => {
      alert('Commit request failed: ' + err);
    });
  });

});

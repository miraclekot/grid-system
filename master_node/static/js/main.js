(function() {
    // ---------- Глобальное состояние ----------
    let currentMatrix = [];
    let rows = 0;
    let cols = 0;

    // DOM элементы
    const matrixContainer = document.getElementById('matrixContainer');
    const matrixDimensionsSpan = document.getElementById('matrix-dimensions');
    const matrixFileInput = document.getElementById('matrixFileInput');
    const wordsTextarea = document.getElementById('wordsListInput');
    const matrixScrollWrapper = document.getElementById('matrixScrollWrapper');
    
    // Функция для показа уведомления
    function showNotification(message, isError = false) {
        const notification = document.createElement('div');
        notification.className = 'toast-notification';
        notification.textContent = message;
        notification.style.background = isError ? '#dc2626' : '#10b981';
        document.body.appendChild(notification);
        setTimeout(() => notification.remove(), 2500);
    }

    // ========== DRAG & DROP ДЛЯ МАТРИЦЫ ==========
    function setupDragAndDropForMatrix() {
        const matrixArea = matrixScrollWrapper;
        
        // Визуальный фидбек при наведении на область матрицы
        matrixArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.stopPropagation();
            matrixArea.classList.add('drag-over');
        });
        
        matrixArea.addEventListener('dragleave', (e) => {
            e.preventDefault();
            e.stopPropagation();
            matrixArea.classList.remove('drag-over');
        });
        
        // Обработка сброса файла в область матрицы
        matrixArea.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            matrixArea.classList.remove('drag-over');
            
            const files = e.dataTransfer.files;
            if (files && files.length > 0) {
                const file = files[0];
                // Проверяем, что это текстовый файл
                if (file.type === 'text/plain' || file.name.toLowerCase().endsWith('.txt') || file.name.toLowerCase().endsWith('.csv')) {
                    const reader = new FileReader();
                    reader.onload = function(event) {
                        const content = event.target.result;
                        const parsed = parseMatrixFromText(content);
                        if (parsed.length === 0) {
                            showNotification('❌ Файл не содержит корректных данных для матрицы', true);
                            return;
                        }
                        setMatrix(parsed);
                        showNotification(`✅ Матрица загружена из ${file.name} (${rows}×${cols})`, false);
                    };
                    reader.onerror = function() {
                        showNotification('❌ Ошибка чтения файла', true);
                    };
                    reader.readAsText(file, 'UTF-8');
                } else {
                    showNotification('❌ Пожалуйста, перетащите файл в формате .txt или .csv', true);
                }
            }
        });
    }
    
    // ========== DRAG & DROP ДЛЯ ТЕКСТОВОГО ПОЛЯ СО СЛОВАМИ ==========
    function setupDragAndDropForWords() {
        // Глобальное предотвращение стандартного поведения браузера для всех элементов
        document.body.addEventListener('dragover', function(e) {
            e.preventDefault();
            e.stopPropagation();
        });
        
        document.body.addEventListener('drop', function(e) {
            e.preventDefault();
            e.stopPropagation();
        });
        
        const textarea = wordsTextarea;
        
        // Визуальный фидбек при наведении на текстовое поле
        textarea.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.stopPropagation();
            textarea.classList.add('drag-over');
        });
        
        textarea.addEventListener('dragleave', (e) => {
            e.preventDefault();
            e.stopPropagation();
            textarea.classList.remove('drag-over');
        });
        
        // Обработка сброса файла
        textarea.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            textarea.classList.remove('drag-over');
            
            const files = e.dataTransfer.files;
            if (files && files.length > 0) {
                const file = files[0];
                if (file.type === 'text/plain' || file.name.toLowerCase().endsWith('.txt')) {
                    const reader = new FileReader();
                    reader.onload = function(event) {
                        const fileContent = event.target.result;
                        wordsTextarea.value = fileContent;
                        const inputEvent = new Event('input', { bubbles: true });
                        wordsTextarea.dispatchEvent(inputEvent);
                        
                        const wordCount = fileContent.split(/\r?\n/).filter(line => line.trim().length > 0).length;
                        showNotification(`✅ Загружено ${file.name} (${wordCount} слов)`, false);
                    };
                    reader.onerror = function() {
                        showNotification('❌ Ошибка чтения файла', true);
                    };
                    reader.readAsText(file, 'UTF-8');
                } else {
                    showNotification('❌ Пожалуйста, перетащите файл в формате .txt', true);
                }
            }
        });
    }
    
    // ========== ФУНКЦИИ ДЛЯ МАТРИЦЫ ==========
    
    function renderMatrix() {
        if (!currentMatrix || rows === 0 || cols === 0) {
            matrixContainer.innerHTML = `
                <div class="empty-matrix-message">
                    📂 Нет загруженной матрицы<br>
                    используйте загрузчик справа<br><br>
                    🖱️ Или перетащите txt файл в эту область
                </div>
            `;
            matrixDimensionsSpan.innerText = `0×0`;
            return;
        }

        const table = document.createElement('table');
        table.className = 'matrix-grid';
        table.cellSpacing = "0";
        table.cellPadding = "0";

        for (let i = 0; i < rows; i++) {
            const tr = document.createElement('tr');
            for (let j = 0; j < cols; j++) {
                const td = document.createElement('td');
                let cellValue = currentMatrix[i][j];
                if (typeof cellValue === 'string' && cellValue.length > 1) {
                    cellValue = cellValue.charAt(0);
                }
                td.textContent = cellValue ? cellValue.toUpperCase() : '?';
                td.setAttribute('data-row', i);
                td.setAttribute('data-col', j);
                tr.appendChild(td);
            }
            table.appendChild(tr);
        }

        matrixContainer.innerHTML = '';
        matrixContainer.appendChild(table);
        matrixDimensionsSpan.innerText = `${rows}×${cols}`;
    }

    function parseMatrixFromText(text) {
        const lines = text.split(/\r?\n/).filter(line => line.trim().length > 0);
        if (lines.length === 0) return [];

        const parsedRows = [];
        let maxCols = 0;

        for (let line of lines) {
            line = line.trim();
            let rowSymbols = [];

            if (line.includes(' ') || line.includes(',') || line.includes('\t')) {
                const parts = line.split(/[\s,]+/);
                for (let part of parts) {
                    if (part.length === 0) continue;
                    if (part.length === 1) {
                        rowSymbols.push(part);
                    } else {
                        for (let ch of part) {
                            rowSymbols.push(ch);
                        }
                    }
                }
            } else {
                for (let ch of line) {
                    rowSymbols.push(ch);
                }
            }

            if (rowSymbols.length > 0) {
                parsedRows.push(rowSymbols);
                if (rowSymbols.length > maxCols) maxCols = rowSymbols.length;
            }
        }

        if (parsedRows.length > 0 && maxCols > 0) {
            for (let i = 0; i < parsedRows.length; i++) {
                while (parsedRows[i].length < maxCols) {
                    parsedRows[i].push(' ');
                }
            }
        }
        return parsedRows;
    }

    function setMatrix(matrix2D) {
        if (!matrix2D || matrix2D.length === 0) {
            currentMatrix = [];
            rows = 0;
            cols = 0;
            renderMatrix();
            return;
        }
        currentMatrix = matrix2D;
        rows = currentMatrix.length;
        cols = rows > 0 ? currentMatrix[0].length : 0;
        
        for (let i = 0; i < rows; i++) {
            if (currentMatrix[i].length !== cols) {
                if (currentMatrix[i].length < cols) {
                    while(currentMatrix[i].length < cols) currentMatrix[i].push(' ');
                } else {
                    currentMatrix[i] = currentMatrix[i].slice(0, cols);
                }
            }
        }
        renderMatrix();
    }

    function handleMatrixFile(file) {
        if (!file) return;
        const reader = new FileReader();
        reader.onload = function(e) {
            const content = e.target.result;
            const parsed = parseMatrixFromText(content);
            if (parsed.length === 0) {
                showNotification('❌ Файл не содержит корректных данных для матрицы', true);
                return;
            }
            setMatrix(parsed);
            showNotification(`📊 Матрица загружена: ${rows}×${cols}`, false);
        };
        reader.onerror = function() {
            showNotification('❌ Ошибка чтения файла', true);
        };
        reader.readAsText(file, 'UTF-8');
    }

    matrixFileInput.addEventListener('change', (event) => {
        const file = event.target.files[0];
        if (file) {
            handleMatrixFile(file);
        }
    });

    // Инициализация Drag & Drop для обоих компонентов
    setupDragAndDropForMatrix();
    setupDragAndDropForWords();
    
    // Слушатель изменения списка слов
    wordsTextarea.addEventListener('input', function() {
        const rawWords = wordsTextarea.value;
        const wordsList = rawWords.split(/\r?\n/).filter(w => w.trim().length > 0);
        console.log('[INFO] Список слов обновлен. Количество слов:', wordsList.length);
        
        const hintElement = document.getElementById('wordsDropHint');
        if (hintElement && wordsList.length > 0) {
            const originalText = hintElement.innerHTML;
            hintElement.innerHTML = `✅ Загружено слов: ${wordsList.length}`;
            hintElement.style.background = '#d1fae5';
            setTimeout(() => {
                hintElement.innerHTML = originalText;
                hintElement.style.background = '#f1f5f9';
            }, 2000);
        }
    });
    
    // Добавляем пример матрицы и слов
    const extraBlock = document.getElementById('extraSettingsPlaceholder');
    if (extraBlock) {
        const demoButtonWrapper = document.createElement('div');
        demoButtonWrapper.style.marginTop = '8px';
        
        const demoBtnMatrix = document.createElement('button');
        demoBtnMatrix.textContent = '📋 Загрузить пример матрицы (4x4)';
        demoBtnMatrix.style.width = '100%';
        demoBtnMatrix.style.background = '#eef2ff';
        demoBtnMatrix.style.borderRadius = '40px';
        demoBtnMatrix.style.padding = '8px';
        demoBtnMatrix.style.cursor = 'pointer';
        demoBtnMatrix.style.fontWeight = '500';
        demoBtnMatrix.style.marginBottom = '8px';
        demoBtnMatrix.onclick = () => {
            const exampleMatrix = [
                ['А', 'Б', 'В', 'Г'],
                ['Д', 'Е', 'Ё', 'Ж'],
                ['З', 'И', 'Й', 'К'],
                ['Л', 'М', 'Н', 'О']
            ];
            setMatrix(exampleMatrix);
            showNotification('✓ Пример матрицы 4x4 загружен', false);
        };
        
        const demoBtnWords = document.createElement('button');
        demoBtnWords.textContent = '📝 Загрузить пример слов';
        demoBtnWords.style.width = '100%';
        demoBtnWords.style.background = '#eef2ff';
        demoBtnWords.style.borderRadius = '40px';
        demoBtnWords.style.padding = '8px';
        demoBtnWords.style.cursor = 'pointer';
        demoBtnWords.style.fontWeight = '500';
        demoBtnWords.onclick = () => {
            const exampleWords = `ПРИВЕТ\nМИР\nКРОТ\nАБАКУС\nМАТРИЦА\nБУКВА\nСЛОВО`;
            wordsTextarea.value = exampleWords;
            const inputEvent = new Event('input', { bubbles: true });
            wordsTextarea.dispatchEvent(inputEvent);
            showNotification('✓ Пример слов загружен (7 слов)', false);
        };
        
        demoButtonWrapper.appendChild(demoBtnMatrix);
        demoButtonWrapper.appendChild(demoBtnWords);
        extraBlock.appendChild(demoButtonWrapper);
    }
    
    // Инициализация
    setMatrix([]);
    
    console.log('✅ Компонент готов: Drag & Drop работает для матрицы и для списка слов!');
    console.log('💡 Перетащите txt файл в матрицу слева или в поле слов справа');
    
    // Подсказка для пользователя
    setTimeout(() => {
        showNotification('💡 Перетащите .txt файл в матрицу слева или в поле слов справа!', false);
    }, 1000);
})();
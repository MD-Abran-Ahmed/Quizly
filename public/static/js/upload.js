/**
 * QUIZLY – PDF UPLOAD & DOCUMENT MANAGEMENT
 */

document.addEventListener('DOMContentLoaded', () => {
  const dropZone = document.getElementById('dropZone');
  const fileInput = document.getElementById('fileInput');
  const filePreview = document.getElementById('filePreview');
  const previewFilename = document.getElementById('previewFilename');
  const previewFilesize = document.getElementById('previewFilesize');
  const removeFileBtn = document.getElementById('removeFileBtn');
  const uploadBtn = document.getElementById('uploadBtn');
  const progressBarContainer = document.getElementById('uploadProgressContainer');
  const progressBarFill = document.getElementById('uploadProgressBar');
  const uploadStatusText = document.getElementById('uploadStatusText');

  let selectedFile = null;

  if (dropZone && fileInput) {
    // Open file browser on drop zone click
    dropZone.addEventListener('click', (e) => {
      if (e.target !== removeFileBtn && !removeFileBtn?.contains(e.target) && e.target !== uploadBtn && !uploadBtn?.contains(e.target)) {
        fileInput.click();
      }
    });

    // Drag-over styling
    ['dragenter', 'dragover'].forEach(eventName => {
      dropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.add('dragover');
      });
    });

    ['dragleave', 'drop'].forEach(eventName => {
      dropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.remove('dragover');
      });
    });

    // Handle dropped files
    dropZone.addEventListener('drop', (e) => {
      const files = e.dataTransfer.files;
      if (files && files.length > 0) {
        handleFileSelection(files[0]);
      }
    });

    // Handle standard file selection
    fileInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files.length > 0) {
        handleFileSelection(e.target.files[0]);
      }
    });

    // Remove selected file
    if (removeFileBtn) {
      removeFileBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        clearFileSelection();
      });
    }

    // Submit upload
    if (uploadBtn) {
      uploadBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (!selectedFile) {
          Quizly.showToast('Please select a PDF file first.', 'warning');
          return;
        }
        performUpload(selectedFile);
      });
    }
  }

  function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  function handleFileSelection(file) {
    if (file.name.toLowerCase().endsWith('.csv')) {
      Quizly.showToast('Detected CSV file! Redirecting to CSV Question Importer...', 'info');
      setTimeout(() => {
        window.location.href = '/create?mode=csv';
      }, 600);
      return;
    }

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      Quizly.showToast('Invalid file format. Please upload a PDF (.pdf) or switch to the CSV tab.', 'error');
      return;
    }

    const maxSize = 25 * 1024 * 1024; // 25 MB
    if (file.size > maxSize) {
      Quizly.showToast('File is too large. Maximum supported size is 25MB.', 'error');
      return;
    }

    selectedFile = file;
    if (previewFilename) previewFilename.textContent = file.name;
    if (previewFilesize) previewFilesize.textContent = formatBytes(file.size);

    if (filePreview) filePreview.style.display = 'flex';
    if (uploadBtn) uploadBtn.style.display = 'inline-flex';
  }

  function clearFileSelection() {
    selectedFile = null;
    if (fileInput) fileInput.value = '';
    if (filePreview) filePreview.style.display = 'none';
    if (uploadBtn) uploadBtn.style.display = 'none';
    if (progressBarContainer) progressBarContainer.style.display = 'none';
    if (progressBarFill) progressBarFill.style.width = '0%';
  }

  function performUpload(file) {
    const formData = new FormData();
    formData.append('file', file);

    if (progressBarContainer) progressBarContainer.style.display = 'block';
    if (uploadBtn) {
      uploadBtn.disabled = true;
      uploadBtn.innerHTML = '<span class="spinner"></span> Extracting Notes...';
    }

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/documents/upload', true);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        const percent = Math.round((e.loaded / e.total) * 90);
        if (progressBarFill) progressBarFill.style.width = `${percent}%`;
        if (uploadStatusText) uploadStatusText.textContent = `Uploading: ${percent}%`;
      }
    };

    xhr.onload = () => {
      if (progressBarFill) progressBarFill.style.width = '100%';

      try {
        const res = JSON.parse(xhr.responseText);
        if (xhr.status >= 200 && xhr.status < 300 && res.success) {
          Quizly.showToast(res.message || 'PDF analyzed successfully!', 'success');
          setTimeout(() => {
            if (res.setup_url) {
              window.location.href = res.setup_url;
            } else {
              window.location.href = '/documents';
            }
          }, 600);
        } else {
          Quizly.showToast(res.message || 'Failed to process PDF.', 'error');
          resetUploadState();
        }
      } catch (err) {
        Quizly.showToast('Server returned an unexpected response.', 'error');
        resetUploadState();
      }
    };

    xhr.onerror = () => {
      Quizly.showToast('Network error during upload. Please try again.', 'error');
      resetUploadState();
    };

    xhr.send(formData);
  }

  function resetUploadState() {
    if (uploadBtn) {
      uploadBtn.disabled = false;
      uploadBtn.innerHTML = 'Upload & Analyze PDF';
    }
    if (progressBarContainer) progressBarContainer.style.display = 'none';
    if (progressBarFill) progressBarFill.style.width = '0%';
  }
});

// Document Deletion Helper (called globally)
window.deleteDocument = async function(docId, docTitle) {
  if (!confirm(`Are you sure you want to delete "${docTitle}"? Any associated quizzes will also be deleted.`)) {
    return;
  }

  try {
    const res = await fetch(`/api/documents/${docId}`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' }
    });
    const data = await res.json();
    if (data.success) {
      Quizly.showToast('Document deleted.', 'success');
      const row = document.getElementById(`doc-row-${docId}`);
      if (row) {
        row.style.opacity = '0';
        row.style.transform = 'scale(0.95)';
        setTimeout(() => row.remove(), 300);
      } else {
        setTimeout(() => window.location.reload(), 400);
      }
    } else {
      Quizly.showToast(data.message || 'Could not delete document.', 'error');
    }
  } catch (e) {
    Quizly.showToast('Network error occurred.', 'error');
  }
};

// Document Preview Helper
window.previewDocument = async function(docId) {
  try {
    const res = await fetch(`/api/documents/${docId}/preview`);
    const data = await res.json();
    if (data.success) {
      const modal = document.getElementById('previewModal');
      const modalTitle = document.getElementById('modalDocTitle');
      const modalContent = document.getElementById('modalDocContent');
      if (modal && modalTitle && modalContent) {
        modalTitle.textContent = data.filename;
        modalContent.textContent = data.preview;
        modal.style.display = 'flex';
      }
    } else {
      Quizly.showToast(data.message || 'Unable to preview text.', 'warning');
    }
  } catch (e) {
    Quizly.showToast('Error loading preview.', 'error');
  }
};


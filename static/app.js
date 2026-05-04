/** * AI Summary Tool — Frontend Logic * Handles file upload (drag & drop + click), slider controls, * API communication, and dynamic result rendering. */ 
(function () { "use strict"; 
const dropzone = document.getElementById("dropzone"); const fileInput = document.getElementById("file-input"); 
const selectedFileEl = document.getElementById("selected-file"); const fileNameEl = document.getElementById("file-name"); 
const fileSizeEl = document.getElementById("file-size"); const removeFileBtn = document.getElementById("remove-file"); 
const mainPointsSlider = document.getElementById("main-points-slider"); const mainPointsValue = document.getElementById("main-points-value"); 
const summarySlider = document.getElementById("summary-slider"); const summaryValue = document.getElementById("summary-value"); 
const summarizeBtn = document.getElementById("summarize-btn"); const btnText = summarizeBtn.querySelector(".btn-text"); 
const btnLoader = summarizeBtn.querySelector(".btn-loader"); const uploadSection = document.getElementById("upload-section"); 
const resultsSection = document.getElementById("results-section"); const fileStats = document.getElementById("file-stats"); 
const pointsList = document.getElementById("points-list"); const summaryText = document.getElementById("summary-text"); 
const newFileBtn = document.getElementById("new-file-btn"); const errorToast = document.getElementById("error-toast"); 
const toastMessage = document.getElementById("toast-message"); 
let selectedFile = null; let toastTimer = null; 
btnLoader.classList.add("is-hidden"); btnText.classList.remove("is-hidden"); 
function formatBytes(bytes) { if (bytes < 1024) return bytes + " B"; if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB"; return (bytes / 1048576).toFixed(1) + " MB"; } 
function showToast(msg, duration = 4500) { toastMessage.textContent = msg; errorToast.hidden = false; void errorToast.offsetWidth; errorToast.classList.add("visible"); clearTimeout(toastTimer); toastTimer = setTimeout(() => { errorToast.classList.remove("visible"); setTimeout(() => { errorToast.hidden = true; }, 350); }, duration); } 
function isAllowedType(file) { const ext = file.name.split(".").pop().toLowerCase(); return ["txt", "pdf", "docx"].includes(ext); } 
function selectFile(file) { if (!isAllowedType(file)) { showToast("Unsupported file type. Please upload a .txt, .pdf, or .docx file."); return; } selectedFile = file; fileNameEl.textContent = file.name; fileSizeEl.textContent = formatBytes(file.size); selectedFileEl.hidden = false; summarizeBtn.disabled = false; dropzone.style.borderColor = "rgba(52, 211, 153, 0.5)"; setTimeout(() => { dropzone.style.borderColor = ""; }, 800); } 
function clearFile() { selectedFile = null; fileInput.value = ""; selectedFileEl.hidden = true; summarizeBtn.disabled = true; } 
dropzone.addEventListener("click", () => fileInput.click()); 
dropzone.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); } }); 
fileInput.addEventListener("change", () => { if (fileInput.files.length) selectFile(fileInput.files[0]); }); 
removeFileBtn.addEventListener("click", (e) => { e.stopPropagation(); clearFile(); }); 
["dragenter", "dragover"].forEach((ev) => { dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.add("drag-over"); }); }); 
["dragleave", "drop"].forEach((ev) => { dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.remove("drag-over"); }); }); 
dropzone.addEventListener("drop", (e) => { const files = e.dataTransfer.files; if (files.length) selectFile(files[0]); }); 
document.addEventListener("dragover", (e) => e.preventDefault()); 
document.addEventListener("drop", (e) => e.preventDefault()); 
mainPointsSlider.addEventListener("input", () => { mainPointsValue.textContent = mainPointsSlider.value; }); 
summarySlider.addEventListener("input", () => { summaryValue.textContent = summarySlider.value; }); 
function setLoading(isLoading) { if (isLoading) { summarizeBtn.disabled = true; btnText.classList.add("is-hidden"); btnLoader.classList.remove("is-hidden"); } else { summarizeBtn.disabled = false; btnText.classList.remove("is-hidden"); btnLoader.classList.add("is-hidden"); } } 
summarizeBtn.addEventListener("click", async () => { if (!selectedFile) return; setLoading(true); const formData = new FormData(); formData.append("file", selectedFile); formData.append("main_points_count", mainPointsSlider.value); formData.append("summary_sentence_count", summarySlider.value); try { const res = await fetch("/summarize", { method: "POST", body: formData, }); const data = await res.json(); if (!res.ok) { showToast(data.error || "Something went wrong."); setLoading(false); return; } renderResults(data); } catch (err) { showToast("Network error. Make sure the server is running."); console.error(err); setLoading(false); } }); 
function renderResults(data) { setLoading(false); uploadSection.hidden = true; resultsSection.hidden = false; fileStats.innerHTML = `<span>📄 ${escapeHtml(data.filename)}</span> <span>${data.word_count.toLocaleString()} words</span> <span>${data.char_count.toLocaleString()} chars</span>`; pointsList.innerHTML = ""; if (data.main_points && data.main_points.length > 0) { data.main_points.forEach((point, i) => { const li = document.createElement("li"); li.textContent = point; li.style.animationDelay = `${i * 0.1}s`; pointsList.appendChild(li); }); } else { const li = document.createElement("li"); li.textContent = "No key points could be extracted."; li.style.opacity = "0.5"; pointsList.appendChild(li); } summaryText.textContent = data.summary || "No summary could be generated."; resultsSection.scrollIntoView({ behavior: "smooth", block: "start" }); } 
function escapeHtml(str) { const div = document.createElement("div"); div.textContent = str; return div.innerHTML; } 
newFileBtn.addEventListener("click", () => { resultsSection.hidden = true; uploadSection.hidden = false; clearFile(); setLoading(false); uploadSection.style.animation = "none"; void uploadSection.offsetWidth; uploadSection.style.animation = ""; }); 
})();

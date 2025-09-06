import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import '../Styles/App.css';

// Используем относительные пути; CRA проксирует на контейнер `server:5000`

function App() {
  const [file, setFile] = useState(null);
  const [slides, setSlides] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [view, setView] = useState('upload'); // upload | ready | countdown | presenting
  const [currentIndex, setCurrentIndex] = useState(0);
  const timerRef = useRef(null);
  const [countdown, setCountdown] = useState(null); // 3 -> 2 -> 1
  const countdownRef = useRef(null);
  const [slideSize, setSlideSize] = useState({ w: 16, h: 9 }); // keep consistent aspect
  // Audio recording and per-slide timing
  const mediaStreamRef = useRef(null);
  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const recordingSlideIndexRef = useRef(null); // 1-based slide number for current recording
  const navBusyRef = useRef(false); // guard against fast double clicks
  const [slideDurations, setSlideDurations] = useState([]); // completed slides [{index, seconds}]
  const [currentSlideSeconds, setCurrentSlideSeconds] = useState(0);
  const [analysisMode, setAnalysisMode] = useState(null); // 'per-slide' | 'full'
  const [audioMap, setAudioMap] = useState({}); // { [index]: path }
  const [transcripts, setTranscripts] = useState({}); // { [index]: { open, loading, text, error } }
  const [extraInfo, setExtraInfo] = useState('');
  const [slideAI, setSlideAI] = useState({}); // { [index]: { loading, feedback, tips[], error } }
  const [summaryAI, setSummaryAI] = useState({ loading: false, feedback: null, tips: null, error: null });
  const [showSlideReportModal, setShowSlideReportModal] = useState(false);
  const [modalReport, setModalReport] = useState(null); // {index, seconds, audioPath}
  const pendingNextIndexRef = useRef(null);
  const [micDevices, setMicDevices] = useState([]);
  const [selectedMicId, setSelectedMicId] = useState('');
  const [micStatus, setMicStatus] = useState(''); // '', 'ok', 'denied', 'not-found', 'error'
  const micInitRequestedRef = useRef(false);
  const nextSlideRef = useRef(() => {});
  const prevSlideRef = useRef(() => {});

  useEffect(() => {
    const handleKey = (e) => {
      if (view !== 'presenting') return;
      if (showSlideReportModal) return; // disable navigation while modal is open
      if (e.key === 'ArrowRight') nextSlideRef.current();
      if (e.key === 'ArrowLeft') prevSlideRef.current();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [view, showSlideReportModal]);

  const onFileChange = (e) => {
    const f = e.target.files?.[0];
    setFile(f || null);
  };

  const uploadFile = async () => {
    if (!file) return;
    const form = new FormData();
    form.append('file', file);
    try {
      const { data } = await axios.post(`/upload`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setSessionId(data.sessionId);
      setSlides(data.slides);
      setCurrentIndex(0);
      setView('ready');
      // Preload first slide to capture exact aspect ratio
      if (data.slides && data.slides.length) {
        const img = new Image();
        img.onload = () => {
          if (img.naturalWidth && img.naturalHeight) {
            setSlideSize({ w: img.naturalWidth, h: img.naturalHeight });
          }
        };
        img.src = `${data.slides[0]}`;
      }
    } catch (err) {
      alert(err?.response?.data?.detail || 'Ошибка загрузки');
    }
  };

  const startPresentation = () => {
    // reset any previous timers
    if (timerRef.current) clearInterval(timerRef.current);
    if (countdownRef.current) clearInterval(countdownRef.current);

    setView('countdown');
    let c = 3;
    setCountdown(c);
    countdownRef.current = setInterval(() => {
      c -= 1;
      if (c <= 0) {
        clearInterval(countdownRef.current);
        countdownRef.current = null;
        setCountdown(null);
        setView('presenting');
        setCurrentSlideSeconds(0);
        // ticking for global and per-slide time
        timerRef.current = setInterval(() => {
          setCurrentSlideSeconds((s) => s + 1);
        }, 1000);
        // start audio recording for the first slide (1-based)
        startRecording(1);
      } else {
        setCountdown(c);
      }
    }, 1000);
  };

  const stopPresentation = async () => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (countdownRef.current) clearInterval(countdownRef.current);
    // finalize the current slide duration line
    const lastIndex = currentIndex + 1;
    const duration = currentSlideSeconds;
    if (slides.length > 0 && duration >= 0) {
      setSlideDurations((arr) => [...arr, { index: lastIndex, seconds: duration }]);
    }
    // stop and upload last recording, capture path
    const lastPath = await stopAndUploadRecording();
    if (lastPath) {
      setAudioMap((m) => ({ ...m, [lastIndex]: lastPath }));
    }
    // per-slide отчёты отображаются модально, отдельный список не ведём
    // Show summary instead of resetting everything immediately
    setView('summary');
    // When entering summary, fetch AI summary
    fetchSummary();
  };

  const startReview = async (mode) => {
    if (!sessionId) return;
    try {
      const fd = new FormData();
      fd.append('sessionId', sessionId);
      fd.append('mode', mode || 'per-slide');
      fd.append('extraInfo', extraInfo || '');
      await axios.post(`/review/start`, fd);
    } catch (e) {
      console.warn('Не удалось инициализировать рецензию', e);
    }
  };

  const fetchSlideReview = async (index) => {
    if (!sessionId) return;
    setSlideAI((m) => ({ ...m, [index]: { ...(m[index] || {}), loading: true, error: null } }));
    try {
      const fd = new FormData();
      fd.append('sessionId', sessionId);
      fd.append('slideIndex', String(index));
      const { data } = await axios.post(`/review/slide`, fd);
      const feedback = data?.feedback || '';
      const tips = Array.isArray(data?.tips) ? data.tips : [];
      setSlideAI((m) => ({ ...m, [index]: { loading: false, feedback, tips, error: null } }));
    } catch (e) {
      setSlideAI((m) => ({ ...m, [index]: { loading: false, feedback: '', tips: [], error: e?.response?.data?.detail || 'Ошибка запроса' } }));
    }
  };

  const fetchSummary = async () => {
    if (!sessionId) return;
    setSummaryAI({ loading: true, feedback: null, tips: null, error: null });
    try {
      const { data } = await axios.get(`/review/summary`, { params: { sessionId } });
      const feedback = data?.feedback || '';
      const tips = Array.isArray(data?.tips) ? data.tips : [];
      setSummaryAI({ loading: false, feedback, tips, error: null });
    } catch (e) {
      setSummaryAI({ loading: false, feedback: null, tips: null, error: e?.response?.data?.detail || 'Ошибка запроса' });
    }
  };

  const finalizeCurrentSlideAndRecord = async (newIndex) => {
    if (navBusyRef.current) return;
    navBusyRef.current = true;
    // finalize duration for current slide
    const currentOneBased = currentIndex + 1;
    const duration = currentSlideSeconds;
    if (slides.length > 0) {
      setSlideDurations((arr) => {
        // push completed line for the slide we just left
        const next = [...arr, { index: currentOneBased, seconds: duration }];
        return next;
      });
    }
    setCurrentSlideSeconds(0);
    // stop and upload current recording asynchronously, don't block navigation
    // mark audio as pending to reflect status in UI
    setAudioMap((m) => ({ ...m, [currentOneBased]: m[currentOneBased] || 'pending' }));
    const uploadPromise = stopAndUploadRecording();
    Promise.resolve(uploadPromise)
      .then((audioPath) => {
        if (audioPath) {
          setAudioMap((m) => ({ ...m, [currentOneBased]: audioPath }));
          // trigger AI slide review after audio is ready
          if (analysisMode === 'per-slide') {
            fetchSlideReview(currentOneBased);
          }
        } else {
          // keep as pending until user retries or it is unavailable
          setAudioMap((m) => ({ ...m, [currentOneBased]: m[currentOneBased] === 'pending' ? null : m[currentOneBased] }));
        }
      })
      .catch(() => {
        setAudioMap((m) => ({ ...m, [currentOneBased]: null }));
      });
    if (analysisMode === 'per-slide') {
      // пауза и показ модального отчёта по слайду
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      setModalReport({ index: currentOneBased, seconds: duration });
      setShowSlideReportModal(true);
      pendingNextIndexRef.current = newIndex;
      // запрос рецензии запустится, когда аудио сохранится (см. выше)
    }
    // Switch slide in background (no recording until resume)
    setCurrentIndex(newIndex);
    if (analysisMode !== 'per-slide') {
      // give recorder a short moment to stop and release
      setTimeout(() => startRecording(newIndex + 1), 50);
    }
    // allow subsequent navigation
    navBusyRef.current = false;
  };

  const nextSlide = async () => {
    if (currentIndex >= slides.length - 1) return;
    await finalizeCurrentSlideAndRecord(currentIndex + 1);
  };
  const prevSlide = async () => {
    if (currentIndex <= 0) return;
    await finalizeCurrentSlideAndRecord(currentIndex - 1);
  };

  // Обновляем ref, чтобы обработчик клавиатуры видел актуальные функции
  useEffect(() => {
    nextSlideRef.current = nextSlide;
    prevSlideRef.current = prevSlide;
  });

  const formatTime = (t) => {
    const m = Math.floor(t / 60).toString().padStart(2, '0');
    const s = (t % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  const ensureMic = async () => {
    if (!navigator.mediaDevices?.getUserMedia) return null;
    if (!mediaStreamRef.current) {
      try {
        const constraints = selectedMicId
          ? { audio: { deviceId: { exact: selectedMicId } } }
          : { audio: true };
        mediaStreamRef.current = await navigator.mediaDevices.getUserMedia(constraints);
        setMicStatus('ok');
      } catch (e) {
        console.warn('Доступ к микрофону запрещен или не удалось получить устройство', e);
        mediaStreamRef.current = null;
        if (e && (e.name === 'NotFoundError' || e.name === 'OverconstrainedError')) setMicStatus('not-found');
        else if (e && (e.name === 'NotAllowedError' || e.name === 'SecurityError')) setMicStatus('denied');
        else setMicStatus('error');
      }
    }
    return mediaStreamRef.current;
  };

  const enumerateMics = async () => {
    if (!navigator.mediaDevices?.enumerateDevices) return [];
    const devices = await navigator.mediaDevices.enumerateDevices();
    const mics = devices.filter((d) => d.kind === 'audioinput');
    setMicDevices(mics);
    if (!selectedMicId && mics.length > 0) setSelectedMicId(mics[0].deviceId);
    return mics;
  };

  const checkMic = async () => {
    // Prompt for permission then list devices with labels
    setMicStatus('');
    mediaStreamRef.current = null;
    await ensureMic();
    const mics = await enumerateMics();
    if (!mics || mics.length === 0) setMicStatus('not-found');
  };

  // Автозапрос доступа к микрофону при первом рендере
  useEffect(() => {
    if (!micInitRequestedRef.current) {
      micInitRequestedRef.current = true;
      (async () => {
        setMicStatus('');
        mediaStreamRef.current = null;
        await ensureMic();
        const mics = await enumerateMics();
        if (!mics || mics.length === 0) setMicStatus('not-found');
      })();
    }
  }, []);

  const pickMimeType = () => {
    const preferred = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/ogg;codecs=opus',
      'audio/ogg',
      'audio/mp4',
      'audio/aac',
    ];
    for (const t of preferred) {
      if (window.MediaRecorder && MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(t)) return t;
    }
    return undefined;
  };

  const startRecording = async (slideOneBased) => {
    const stream = await ensureMic();
    if (!stream || !window.MediaRecorder) return;
    try {
      chunksRef.current = [];
      const mime = pickMimeType();
      const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      recorderRef.current = rec;
      recordingSlideIndexRef.current = slideOneBased;
      rec.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) chunksRef.current.push(e.data);
      };
      // timeslice to ensure dataavailable fires periodically across browsers
      rec.start(1000);
    } catch (e) {
      console.warn('Не удалось начать запись', e);
      recorderRef.current = null;
      recordingSlideIndexRef.current = null;
    }
  };

  const stopAndUploadRecording = async () => {
    const rec = recorderRef.current;
    if (!rec) return;
    if (rec.state === 'inactive') return;
    const slideOneBased = recordingSlideIndexRef.current;
    const stopped = new Promise((resolve) => {
      rec.onstop = resolve;
    });
    try {
      rec.stop();
      await stopped;
    } catch (e) {
      console.warn('Не удалось остановить запись', e);
    }
    recorderRef.current = null;
    recordingSlideIndexRef.current = null;

    try {
      const mime = (rec && rec.mimeType) || 'audio/webm';
      const blob = new Blob(chunksRef.current, { type: mime });
      chunksRef.current = [];
      if (!blob || blob.size === 0 || !sessionId || !slideOneBased) return;
      const fd = new FormData();
      fd.append('sessionId', sessionId);
      fd.append('slideIndex', String(slideOneBased));
      let ext = 'webm';
      if (mime.includes('ogg')) ext = 'ogg';
      else if (mime.includes('mp4') || mime.includes('aac')) ext = 'm4a';
      fd.append('file', blob, `slide-${slideOneBased}.${ext}`);
      const { data } = await axios.post(`/audio`, fd);
      // Preload transcript state entry as closed; actual fetch on demand
      try {
        if (data && slideOneBased) {
          setTranscripts((m) => ({
            ...m,
            [slideOneBased]: m[slideOneBased] || { open: false, loading: false, text: null, error: null },
          }));
        }
      } catch (_) { /* noop */ }
      return data?.path || null;
    } catch (e) {
      console.warn('Не удалось отправить аудио', e);
    }
  };

  const toggleTranscript = async (idx) => {
    setTranscripts((m) => {
      const current = m[idx] || { open: false, loading: false, text: null, error: null };
      return { ...m, [idx]: { ...current, open: !current.open } };
    });
    // If opening and not loaded yet, fetch
    const entry = transcripts[idx];
    const willOpen = !(entry && entry.open);
    if (willOpen) {
      setTranscripts((m) => ({
        ...m,
        [idx]: { ...(m[idx] || {}), open: true, loading: true, error: null },
      }));
      try {
        const { data } = await axios.get(`/transcript`, { params: { sessionId, slideIndex: idx } });
        const text = (data && (data.polished || data.raw)) || '';
        setTranscripts((m) => ({
          ...m,
          [idx]: { ...(m[idx] || {}), loading: false, text },
        }));
      } catch (e) {
        setTranscripts((m) => ({
          ...m,
          [idx]: { ...(m[idx] || {}), loading: false, error: e?.response?.data?.detail || 'Ошибка получения транскрипта' },
        }));
      }
    }
  };

  const handleContinueAfterReport = () => {
    setShowSlideReportModal(false);
    const idx = pendingNextIndexRef.current;
    pendingNextIndexRef.current = null;
    // resume timers
    if (!timerRef.current) {
      timerRef.current = setInterval(() => {
        setCurrentSlideSeconds((s) => s + 1);
      }, 1000);
    }
    // start recording for the now-active slide
    startRecording((idx ?? currentIndex) + 1);
  };

  const redoSlide = (slideOneBased) => {
    // Close modal and reset to re-record the requested slide
    setShowSlideReportModal(false);
    pendingNextIndexRef.current = null;
    if (timerRef.current) clearInterval(timerRef.current);
    // remove previous duration entries for this slide
    setSlideDurations((arr) => arr.filter((d) => d.index !== slideOneBased));
    // clear previous AI/transcript/audio for the slide
    setTranscripts((m) => { const n = { ...m }; delete n[slideOneBased]; return n; });
    setSlideAI((m) => { const n = { ...m }; delete n[slideOneBased]; return n; });
    setAudioMap((m) => ({ ...m, [slideOneBased]: 'pending' }));
    // jump back to that slide and start recording anew
    setView('presenting');
    setCurrentIndex(slideOneBased - 1);
    setCurrentSlideSeconds(0);
    timerRef.current = setInterval(() => setCurrentSlideSeconds((s) => s + 1), 1000);
    setTimeout(() => startRecording(slideOneBased), 50);
  };

  const redoPresentation = async () => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (countdownRef.current) clearInterval(countdownRef.current);
    // reset state, keep session and slides
    setSlideDurations([]);
    setAudioMap({});
    setTranscripts({});
    setSlideAI({});
    setSummaryAI({ loading: false, feedback: null, tips: null, error: null });
    setCurrentIndex(0);
    setCurrentSlideSeconds(0);
    // restart same analysis mode
    await startReview(analysisMode || 'per-slide');
    startPresentation();
  };

  return (
    <div className="app">
      <h2 className="title">Слайды из PDF/PPTX</h2>

      {view === 'upload' && (
        <div style={{ textAlign: 'center' }}>
          <div className="row" style={{ marginBottom: 12 }}>
            <input className="file-input" type="file" accept=".pdf,.pptx" onChange={onFileChange} />
            <button className="btn btn-primary" disabled={!file} onClick={uploadFile}>Загрузить</button>
          </div>
          <div className="row" style={{ marginBottom: 8 }}>
            <button className="btn" onClick={checkMic}>Проверить микрофон</button>
            {micStatus === 'ok' && <span className="badge" style={{ color: '#16a34a' }}>Микрофон готов</span>}
            {micStatus === 'denied' && <span className="badge" style={{ color: '#dc2626' }}>Доступ запрещен</span>}
            {micStatus === 'not-found' && <span className="badge" style={{ color: '#dc2626' }}>Микрофон не найден</span>}
            {micStatus === 'error' && <span className="badge" style={{ color: '#ea580c' }}>Ошибка микрофона</span>}
          </div>
          {micDevices.length > 0 && (
            <div className="row">
              <label className="badge">Устройство:</label>
              <select className="btn" value={selectedMicId} onChange={(e) => { setSelectedMicId(e.target.value); mediaStreamRef.current = null; }}>
                {micDevices.map((d) => (
                  <option key={d.deviceId} value={d.deviceId}>{d.label || `Микрофон ${d.deviceId.slice(0,6)}`}</option>
                ))}
              </select>
            </div>
          )}
        </div>
      )}

      {view === 'ready' && (
        <div style={{ textAlign: 'center' }}>
          <p className="muted">Файл загружен. Слайдов: {slides.length}</p>
          <div className="row" style={{ marginBottom: 12, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <label className="badge" style={{ alignSelf: 'flex-start' }}>Дополнительная информация по презентации</label>
            <textarea
              className="file-input"
              style={{ width: '100%', maxWidth: 720, minHeight: 90 }}
              placeholder="Цель, аудитория, контекст, что важно подчеркнуть..."
              value={extraInfo}
              onChange={(e) => setExtraInfo(e.target.value)}
            />
          </div>
          <div className="row">
            <button className="btn" onClick={() => setView('upload')}>Поменять файл</button>
            <button className="btn btn-primary" onClick={async () => { setAnalysisMode('per-slide'); await startReview('per-slide'); startPresentation(); }}>Разобрать по слайдам</button>
            <button className="btn" onClick={async () => { setAnalysisMode('full'); await startReview('full'); startPresentation(); }}>Разобрать целиком</button>
          </div>
        </div>
      )}

      {(view === 'countdown' || view === 'presenting') && (
        <div>
          <div className="topbar">
            <button className="btn" onClick={prevSlide} disabled={currentIndex === 0 || view === 'countdown' || showSlideReportModal}>&larr; Назад</button>
            <div className="badge">Слайд {slides.length ? currentIndex + 1 : 0} / {slides.length}</div>
            {currentIndex === slides.length - 1 ? (
              <button className="btn btn-primary" onClick={stopPresentation} disabled={view === 'countdown' || showSlideReportModal}>Завершить</button>
            ) : (
              <button className="btn" onClick={nextSlide} disabled={view === 'countdown' || showSlideReportModal}>Вперёд &rarr;</button>
            )}
          </div>

          <div className="slide-frame" style={{ aspectRatio: `${slideSize.w} / ${slideSize.h}` }}>
            {view === 'presenting' && slides[currentIndex] && (
              <img className="slide-img" src={`${slides[currentIndex]}`} alt={`slide-${currentIndex + 1}`} />
            )}

            {view === 'countdown' && (
              <div className="overlay overlay-countdown">
                <div className="num">{countdown ?? 3}</div>
              </div>
            )}
          </div>

          {/* per-slide inline reports removed; shown as modal instead */}

          <div className="panel">
            {slideDurations.map((d, i) => (
              <div key={`dur-${d.index}-${i}`}>{`Слайд ${d.index} - ${formatTime(d.seconds)}`}</div>
            ))}
            <div>{`Слайд ${currentIndex + 1} - ${formatTime(currentSlideSeconds)}`}</div>
          </div>
        </div>
      )}

      {showSlideReportModal && modalReport && (
        <div className="modal">
          <div className="modal-card">
            <h3 className="modal-title">{`Отчет по слайду ${modalReport.index}`}</h3>
            <div className="card">
              <div style={{ marginBottom: 8 }}>Время: {formatTime(modalReport.seconds)}</div>
              {audioMap[modalReport.index] === 'pending' && (
                <div className="muted">Аудио обрабатывается…</div>
              )}
              {audioMap[modalReport.index] && audioMap[modalReport.index] !== 'pending' ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <div className="muted">Аудио:</div>
                  <audio controls preload="none" src={`${audioMap[modalReport.index]}`}></audio>
                </div>
              ) : null}
              {!audioMap[modalReport.index] && audioMap[modalReport.index] !== 'pending' && (
                <div className="muted">Аудио: недоступно</div>
              )}
              <div style={{ marginTop: 8 }}>
                <div className="muted">AI-оценка:</div>
                {slideAI[modalReport.index]?.loading && <div className="muted">Загрузка...</div>}
                {slideAI[modalReport.index]?.error && <div className="muted" style={{ color: '#dc2626' }}>{slideAI[modalReport.index].error}</div>}
                {(!slideAI[modalReport.index]?.loading && !slideAI[modalReport.index]?.error) && (
                  <div>
                    <div style={{ whiteSpace: 'pre-wrap' }}>{slideAI[modalReport.index]?.feedback || '—'}</div>
                    {(slideAI[modalReport.index]?.tips || []).length > 0 && (
                      <ul style={{ marginTop: 6 }}>
                        {(slideAI[modalReport.index].tips).map((t, i) => (<li key={`tip-${modalReport.index}-${i}`}>{t}</li>))}
                      </ul>
                    )}
                  </div>
                )}
              </div>
            </div>
            <div className="modal-footer" style={{ display: 'flex', gap: 8 }}>
              <button className="btn" onClick={() => redoSlide(modalReport.index)}>Перезаписать</button>
              <button className="btn btn-primary" onClick={handleContinueAfterReport}>Продолжить</button>
            </div>
          </div>
        </div>
      )}

      {view === 'summary' && (
        <div className="modal">
          <div className="modal-card">
            <h3 className="modal-title">Отчет о презентации</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div className="card">
                <div style={{ fontWeight: 700, marginBottom: 6 }}>AI — Итоговая оценка</div>
                {summaryAI.loading && <div className="muted">Загрузка...</div>}
                {summaryAI.error && <div className="muted" style={{ color: '#dc2626' }}>{summaryAI.error}</div>}
                {(!summaryAI.loading && !summaryAI.error) && (
                  <div>
                    <div style={{ whiteSpace: 'pre-wrap' }}>{summaryAI.feedback || '—'}</div>
                    {Array.isArray(summaryAI.tips) && summaryAI.tips.length > 0 && (
                      <ul style={{ marginTop: 6 }}>
                        {summaryAI.tips.map((t, i) => (<li key={`sumtip-${i}`}>{t}</li>))}
                      </ul>
                    )}
                  </div>
                )}
              </div>
              {slideDurations.map((d, i) => (
                <div key={`sum-${d.index}-${i}`} className="card">
                  <div style={{ fontWeight: 700, marginBottom: 6 }}>Слайд {d.index}</div>
                  <div>Время: {formatTime(d.seconds)}</div>
                  {audioMap[d.index] === 'pending' ? (
                    <div className="muted">Аудио обрабатывается…</div>
                  ) : audioMap[d.index] ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      <div className="muted">Аудио:</div>
                      <audio controls preload="none" src={`${audioMap[d.index]}`}></audio>
                      <div>
                        <button className="btn" onClick={() => toggleTranscript(d.index)}>
                          {transcripts[d.index]?.open ? 'Скрыть транскрипт' : 'Показать транскрипт'}
                        </button>
                      </div>
                      {transcripts[d.index]?.open && (
                        <div className="card" style={{ background: '#fafafa' }}>
                          {transcripts[d.index]?.loading && <div className="muted">Загрузка...</div>}
                          {transcripts[d.index]?.error && <div className="muted" style={{ color: '#dc2626' }}>{transcripts[d.index].error}</div>}
                          {(!transcripts[d.index]?.loading && !transcripts[d.index]?.error) && (
                            <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.4 }}>
                              {transcripts[d.index]?.text || 'Текст недоступен'}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="muted">Аудио: недоступно</div>
                  )}
                </div>
              ))}
            </div>
            <div className="modal-footer">
              <button className="btn" onClick={() => setView('ready')}>Закрыть</button>
              <button className="btn" onClick={redoPresentation}>Перезаписать</button>
              <button className="btn btn-primary" onClick={() => {
                if (timerRef.current) clearInterval(timerRef.current);
                if (countdownRef.current) clearInterval(countdownRef.current);
                setView('upload');
                setFile(null);
                setSlides([]);
                setSessionId(null);
                setCurrentIndex(0);
                setCountdown(null);
                setSlideDurations([]);
                setCurrentSlideSeconds(0);
                setAnalysisMode(null);
                setAudioMap({});
                setSlideAI({});
                setSummaryAI({ loading: false, feedback: null, tips: null, error: null });
              }}>Новая презентация</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;

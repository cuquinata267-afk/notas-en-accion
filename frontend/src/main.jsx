import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

async function api(path, method = 'GET', data) {
  const response = await fetch(`/api${path}`, {
    method,
    ...(data === undefined ? {} : {
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),
  });
  const payload = response.status === 204 ? null : await response.json();
  if (!response.ok) {
    const message = typeof payload.detail === 'string' ? payload.detail : 'Revisa los datos del formulario.';
    throw Object.assign(new Error(message), { status: response.status });
  }
  return payload;
}

function Brand() {
  return <div className="brand"><span className="brand-mark" aria-hidden="true">✓</span>Notas en Acción</div>;
}

function Login({ onLogin, initialError }) {
  const [error, setError] = useState(initialError);
  const [saving, setSaving] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError('');
    setSaving(true);
    try {
      onLogin(await api('/login', 'POST', Object.fromEntries(new FormData(event.target))));
    } catch (failure) {
      setError(failure.message);
    } finally {
      setSaving(false);
    }
  }

  return <main className="login-page">
    <div className="login-card">
      <Brand />
      <h1>Iniciar sesión</h1>
      <form className="form" onSubmit={submit}>
        <label>Usuario<input name="username" autoComplete="username" required maxLength={40} /></label>
        <label>Contraseña<input name="password" type="password" autoComplete="current-password" required maxLength={128} /></label>
        {error && <p role="alert" className="error">{error}</p>}
        <button className="primary" disabled={saving}>Entrar</button>
      </form>
    </div>
  </main>;
}

function NoteEditor({ note, folders, folderId, saving, onSave, onCancel }) {
  function submit(event) {
    event.preventDefault();
    const { folder_id, title, body, checklist } = Object.fromEntries(new FormData(event.target));
    const data = { folder_id: Number(folder_id), title, body };
    if (checklist !== undefined) data.items = checklist.split('\n').map(item => item.trim()).filter(Boolean);
    onSave(data);
  }

  return <section className="editor" aria-labelledby="editor-title">
    <h2 id="editor-title">{note ? 'Editar nota' : 'Nueva nota'}</h2>
    <form className="form" onSubmit={submit}>
      <label>Título<input name="title" required maxLength={120} defaultValue={note?.title ?? ''} autoFocus /></label>
      <label>Carpeta<select name="folder_id" defaultValue={note?.folder_id ?? folderId ?? folders[0].id}>
        {folders.map(folder => <option key={folder.id} value={folder.id}>{folder.name}</option>)}
      </select></label>
      <label>Contenido<textarea name="body" rows={4} maxLength={8000} defaultValue={note?.body ?? ''} /></label>
      {!note && <label>Tareas, una por línea<textarea name="checklist" rows={3} maxLength={4829} /></label>}
      <div className="actions">
        <button className="primary" disabled={saving}>Guardar nota</button>
        <button type="button" onClick={onCancel}>Cancelar</button>
      </div>
    </form>
  </section>;
}

function NoteCard({ note, folder, saving, onEdit, onDelete, onCheck, onAddItem }) {
  const [adding, setAdding] = useState(false);
  const { completed, total } = note.progress;

  async function submitItem(event) {
    event.preventDefault();
    const label = new FormData(event.target).get('label');
    if (await onAddItem(label)) setAdding(false);
  }

  return <article className="note" aria-label={note.title}>
    <div className="note-folder">{folder?.name}</div>
    <h2>{note.title}</h2>
    {note.body && <p className="note-body">{note.body}</p>}
    {total > 0 && <div className="checklist">
      <div className="progress-label">{completed} de {total} completadas</div>
      <progress aria-label="Progreso de tareas" value={completed} max={total} />
      {note.items.map(item => <label key={item.id} className={item.done ? 'checked' : ''}>
        <input type="checkbox" checked={item.done} disabled={saving} onChange={event => onCheck(item, event.target.checked)} />
        {item.label}
      </label>)}
    </div>}
    {adding && <form className="inline-form" onSubmit={submitItem}>
      <input name="label" aria-label="Tarea nueva" required maxLength={160} autoFocus />
      <button disabled={saving}>Añadir</button>
    </form>}
    <div className="note-actions">
      <button onClick={() => setAdding(!adding)}>{adding ? 'Cancelar tarea' : 'Agregar tarea'}</button>
      <button onClick={onEdit} disabled={saving}>Editar</button>
      <button className="danger" onClick={onDelete} disabled={saving}>Borrar</button>
    </div>
  </article>;
}

function Dashboard({ user, onLogout }) {
  const [folders, setFolders] = useState([]);
  const [notes, setNotes] = useState([]);
  const [folderId, setFolderId] = useState(null);
  const [pendingOnly, setPendingOnly] = useState(false);
  const [addingFolder, setAddingFolder] = useState(false);
  const [editor, setEditor] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    Promise.all([api('/folders'), api('/notes')])
      .then(([folderData, noteData]) => { setFolders(folderData); setNotes(noteData); })
      .catch(failure => failure.status === 401 ? onLogout() : setError(failure.message))
      .finally(() => setLoading(false));
  }, []);

  async function change(action) {
    setSaving(true);
    setError('');
    try {
      await action();
      return true;
    } catch (failure) {
      if (failure.status === 401) onLogout();
      else setError(failure.message);
      return false;
    } finally {
      setSaving(false);
    }
  }

  function replaceNote(note) {
    setNotes(current => current.map(row => row.id === note.id ? note : row));
  }

  async function createFolder(event) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.target));
    await change(async () => {
      const folder = await api('/folders', 'POST', data);
      setFolders(current => [...current, folder]);
      setFolderId(folder.id);
      setAddingFolder(false);
    });
  }

  function saveNote(data) {
    change(async () => {
      if (editor.note) replaceNote(await api(`/notes/${editor.note.id}`, 'PUT', data));
      else {
        const note = await api('/notes', 'POST', data);
        setNotes(current => [note, ...current]);
      }
      if (folderId !== null) setFolderId(data.folder_id);
      setPendingOnly(false);
      setEditor(null);
    });
  }

  function deleteNote(note) {
    if (window.confirm(`¿Borrar la nota «${note.title}»?`)) change(async () => {
      await api(`/notes/${note.id}`, 'DELETE');
      setNotes(current => current.filter(row => row.id !== note.id));
      if (editor?.note?.id === note.id) setEditor(null);
    });
  }

  const visible = notes.filter(note => (folderId === null || note.folder_id === folderId)
    && (!pendingOnly || note.progress.completed < note.progress.total));
  const activeFolder = folders.find(folder => folder.id === folderId);

  return <>
    <header className="topbar">
      <Brand />
      <div className="user"><span>{user.username}</span><button disabled={saving} onClick={() => change(async () => {
        await api('/logout', 'POST');
        onLogout();
      })}>Cerrar sesión</button></div>
    </header>
    <div className="workspace">
      <aside>
        <div className="sidebar-head"><h2>Carpetas</h2><button className="square" aria-label="Nueva carpeta" onClick={() => setAddingFolder(!addingFolder)}>+</button></div>
        {addingFolder && <form className="form folder-form" onSubmit={createFolder}>
          <label>Nombre de carpeta<input name="name" required maxLength={60} autoFocus /></label>
          <button disabled={saving}>Crear carpeta</button>
        </form>}
        <nav aria-label="Carpetas" className="folders">
          <button aria-pressed={folderId === null} onClick={() => setFolderId(null)}>Todas las notas <span>{notes.length}</span></button>
          {folders.map(folder => <button key={folder.id} aria-pressed={folderId === folder.id} onClick={() => setFolderId(folder.id)}>
            {folder.name}<span>{notes.filter(note => note.folder_id === folder.id).length}</span>
          </button>)}
        </nav>
      </aside>
      <main className="board">
        <div className="board-head">
          <h1>{activeFolder?.name ?? 'Mis notas'}</h1>
          <button className="primary" disabled={saving || folders.length === 0} onClick={() => setEditor({ note: null })}>+ Nueva nota</button>
        </div>
        <div className="filters" aria-label="Filtrar notas">
          <button aria-pressed={!pendingOnly} onClick={() => setPendingOnly(false)}>Todas</button>
          <button aria-pressed={pendingOnly} onClick={() => setPendingOnly(true)}>Pendientes</button>
        </div>
        {error && <p role="alert" className="error">{error}</p>}
        {editor && <NoteEditor key={editor.note?.id ?? 'new'} note={editor.note} folders={folders} folderId={folderId}
          saving={saving} onSave={saveNote} onCancel={() => setEditor(null)} />}
        {loading ? <p role="status">Cargando notas…</p> : visible.length === 0 && !editor ? <div className="empty">
          <span className="brand-mark" aria-hidden="true">✓</span>
          <h2>{pendingOnly ? 'Sin tareas pendientes' : 'Aún no hay notas'}</h2>
          {!pendingOnly && <p>Usa Nueva nota para empezar.</p>}
        </div> : null}
        <div className="grid">
          {visible.map(note => <NoteCard key={note.id} note={note} folder={folders.find(folder => folder.id === note.folder_id)} saving={saving}
            onEdit={() => setEditor({ note })} onDelete={() => deleteNote(note)}
            onCheck={(item, done) => change(async () => replaceNote(await api(`/notes/${note.id}/items/${item.id}`, 'PATCH', { done })))}
            onAddItem={label => change(async () => replaceNote(await api(`/notes/${note.id}/items`, 'POST', { label })))} />)}
        </div>
      </main>
    </div>
  </>;
}

function App() {
  const [user, setUser] = useState(undefined);
  const [error, setError] = useState('');
  useEffect(() => {
    api('/me').then(setUser).catch(failure => {
      if (failure.status !== 401) setError('La aplicación no pudo conectar con el servidor.');
      setUser(null);
    });
  }, []);
  if (user === undefined) return <p className="loading" role="status">Cargando…</p>;
  return user ? <Dashboard user={user} onLogout={() => setUser(null)} /> : <Login onLogin={setUser} initialError={error} />;
}

createRoot(document.getElementById('root')).render(<App />);

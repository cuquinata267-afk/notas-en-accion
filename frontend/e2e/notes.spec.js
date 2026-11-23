import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Usuario', { exact: true }).fill('demo1');
  await page.getByLabel('Contraseña').fill('notas-demo-1');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page.getByRole('heading', { name: 'Mis notas' })).toBeVisible();
});

async function createNote(page, title, tasks = '') {
  await page.getByRole('button', { name: 'Nueva nota' }).click();
  await page.getByLabel('Título').fill(title);
  await page.getByLabel('Tareas, una por línea').fill(tasks);
  await page.getByRole('button', { name: 'Guardar nota' }).click();
  const card = page.getByRole('article', { name: title, exact: true });
  await expect(card).toBeVisible();
  return card;
}

test('inicia sesión y la cierra', async ({ page }) => {
  await page.getByRole('button', { name: 'Cerrar sesión' }).click();
  await expect(page.getByRole('heading', { name: 'Iniciar sesión' })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Iniciar sesión' })).toBeVisible();
});

test('crea una carpeta y una nota dentro', async ({ page }) => {
  const folder = `Redes ${Date.now()}`;
  await page.getByRole('button', { name: 'Nueva carpeta' }).click();
  await page.getByLabel('Nombre de carpeta').fill(folder);
  await page.getByRole('button', { name: 'Crear carpeta' }).click();
  await expect(page.getByRole('heading', { name: folder })).toBeVisible();
  const note = await createNote(page, `Estudiar VCN ${Date.now()}`);
  await expect(note.getByText(folder, { exact: true })).toBeVisible();
});

test('edita el título y el contenido de una nota', async ({ page }) => {
  const suffix = Date.now();
  const card = await createNote(page, `Borrador ${suffix}`);
  await card.getByRole('button', { name: 'Editar' }).click();
  await page.getByLabel('Título').fill(`Informe ${suffix}`);
  await page.getByLabel('Contenido').fill('Revisar la entrega');
  await page.getByRole('button', { name: 'Guardar nota' }).click();
  await expect(page.getByRole('article', { name: `Informe ${suffix}`, exact: true })).toContainText('Revisar la entrega');
});

test('marca una tarea y mantiene el progreso al recargar', async ({ page }) => {
  const card = await createNote(page, `Checklist ${Date.now()}`, 'Crear VM\nAbrir la app');
  await card.getByRole('checkbox', { name: 'Crear VM' }).check();
  await expect(card.getByText('1 de 2 completadas')).toBeVisible();
  await page.reload();
  await expect(card.getByRole('checkbox', { name: 'Crear VM' })).toBeChecked();
  await expect(card.getByText('1 de 2 completadas')).toBeVisible();
});

test('filtra notas con tareas pendientes', async ({ page }) => {
  const suffix = Date.now();
  const pending = await createNote(page, `Pendiente ${suffix}`, 'Revisar código');
  const completed = await createNote(page, `Lista ${suffix}`, 'Hacer push');
  await completed.getByRole('checkbox', { name: 'Hacer push' }).check();
  await expect(completed.getByText('1 de 1 completadas')).toBeVisible();
  await page.getByRole('button', { name: 'Pendientes', exact: true }).click();
  await expect(pending).toBeVisible();
  await expect(completed).toHaveCount(0);
});

test('borra una nota y el cambio persiste', async ({ page }) => {
  const card = await createNote(page, `Temporal ${Date.now()}`);
  page.once('dialog', dialog => dialog.accept());
  await card.getByRole('button', { name: 'Borrar' }).click();
  await expect(card).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Mis notas' })).toBeVisible();
  await expect(card).toHaveCount(0);
});

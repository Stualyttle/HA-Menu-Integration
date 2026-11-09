import { describe, expect, it } from 'vitest';
import { confirmAction } from '../components/common.js';

describe('confirmAction', () => {
  it('resolves with the app-shell confirmation choice', async () => {
    const host = new EventTarget();
    host.addEventListener('mp-confirm', (event) => {
      expect(event.detail.message).toBe('Delete this category?');
      event.detail.resolve(false);
    });

    await expect(confirmAction(host, 'Delete this category?')).resolves.toBe(false);
  });
});

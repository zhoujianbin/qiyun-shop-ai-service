import { upload } from '../client';
import type { Attachment } from '@/types/domain';

export const attachmentsApi = {
  upload: (file: File, options?: { ownerType?: string; ownerId?: string; isPublic?: boolean }) => {
    const form = new FormData();
    form.append('file', file);
    if (options?.ownerType) form.append('owner_type', options.ownerType);
    if (options?.ownerId) form.append('owner_id', options.ownerId);
    form.append('is_public', String(options?.isPublic ?? false));
    return upload<Attachment>('/attachments', form);
  },
  detail: (id: number) => apiDetail(id),
};

import { api } from '../client';
function apiDetail(id: number) {
  return api.get<Attachment>(`/attachments/${id}`);
}

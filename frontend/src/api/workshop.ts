import { ApiError, getHeaders } from "./client";

const BASE = "";

export interface MediaCreateInput {
  hero_image?: string;
  gallery_images?: string[];
  instructor_image?: string;
  video_url?: string;
  brochure_pdf?: string;
  registration_qr?: string;
}

export interface ProjectCreateInput {
  title: string;
  description: string;
  image_url?: string;
  technology?: string;
}

export interface TimelineStepCreateInput {
  step?: number;
  title: string;
  description: string;
  duration?: string;
}

export interface ContentCreateInput {
  learning_outcomes?: string[];
  highlights?: string[];
  projects?: ProjectCreateInput[];
  journey?: TimelineStepCreateInput[];
}

export interface InstructorCreateInput {
  name?: string;
  role?: string;
  bio?: string;
  photo?: string;
}

export interface RegistrationCreateInput {
  url?: string;
  button_text?: string;
  seats_available?: number;
  deadline?: string;
  contact_email?: string;
  contact_phone?: string;
}

export interface Workshop {
  id: string;
  name: string;
  description?: string;
  date?: string;
  time?: string;
  duration?: string;
  venue?: string;
  age_group?: string;
  price: number;
  topics?: string[];
  poster_path?: string;
  video_url?: string;
  sales_team_email?: string;
  shopify_product_id?: number | null;
  shopify_variant_id?: number | null;
  status: string;
  generated_description?: string;
  seo_metadata?: Record<string, any>;
  marketing?: Record<string, any>;
  media?: MediaCreateInput;
  content?: ContentCreateInput;
  instructor?: InstructorCreateInput;
  registration?: RegistrationCreateInput;
  created_at?: string;
  updated_at?: string;
}

export interface WorkshopCreateInput {
  name: string;
  description: string;
  date?: string;
  time?: string;
  duration?: string;
  venue?: string;
  age_group?: string;
  price: number;
  topics?: string[];
  poster_path?: string;
  video_url?: string;
  sales_team_email?: string;
  media?: MediaCreateInput;
  content?: ContentCreateInput;
  instructor?: InstructorCreateInput;
  registration?: RegistrationCreateInput;
}

export interface RegistrationInput {
  child_name: string;
  child_age: number;
  parent_name: string;
  customer_email: string;
  customer_phone?: string;
  school?: string;
  emergency_contact?: string;
}

export interface RegistrationResult {
  status: string;
  registration_id: string;
  redirect_url: string;
}

export interface UploadMediaResult {
  success: boolean;
  url: string;
  filename: string;
  content_type: string;
  size: number;
}


async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      // ignore
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export const workshopApi = {
  listWorkshops: (): Promise<Workshop[]> =>
    fetch(`${BASE}/api/workshops`, { headers: getHeaders() }).then((r) => asJson<Workshop[]>(r)),

  getWorkshop: (id: string): Promise<Workshop> =>
    fetch(`${BASE}/api/workshops/${id}`, { headers: getHeaders() }).then((r) => asJson<Workshop>(r)),

  createWorkshop: (data: WorkshopCreateInput): Promise<{ success: boolean; workshop_id: string; status: string; message: string }> =>
    fetch(`${BASE}/api/workshops`, {
      method: "POST",
      headers: getHeaders(),
      body: JSON.stringify(data),
    }).then((r) => asJson<{ success: boolean; workshop_id: string; status: string; message: string }>(r)),

  uploadMedia: (file: File, folderName = "workshop_media"): Promise<UploadMediaResult> => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("folder_name", folderName);
    const headers: Record<string, string> = { ...getHeaders() };
    delete headers["Content-Type"]; // Let browser set multipart boundary
    return fetch(`${BASE}/api/workshops/upload-media`, {
      method: "POST",
      headers,
      body: formData,
    }).then((r) => asJson<UploadMediaResult>(r));
  },

  generateWorkshop: (id: string): Promise<{ session_id: string; status_endpoint: string }> =>
    fetch(`${BASE}/api/workshops/${id}/generate`, {
      method: "POST",
      headers: getHeaders(),
    }).then((r) => asJson<{ session_id: string; status_endpoint: string }>(r)),

  approveWorkshop: (id: string): Promise<{
    status: string;
    workshop_id: string;
    current_state: string;
    shopify_product_id: number;
    shopify_variant_id: number;
    product_status: string;
    validation_passed: boolean;
  }> =>
    fetch(`${BASE}/api/workshops/${id}/approve`, {
      method: "POST",
      headers: getHeaders(),
    }).then((r) => asJson<any>(r)),

  publishWorkshop: (id: string): Promise<{
    status: string;
    workshop_id: string;
    shopify_product_id: number;
    shopify_variant_id: number;
    product_status: string;
    db_status: string;
  }> =>
    fetch(`${BASE}/api/workshops/${id}/publish`, {
      method: "POST",
      headers: getHeaders(),
    }).then((r) => asJson<any>(r)),

  registerStudent: (id: string, data: RegistrationInput): Promise<RegistrationResult> =>
    fetch(`${BASE}/api/workshops/${id}/register`, {
      method: "POST",
      headers: getHeaders(),
      body: JSON.stringify(data),
    }).then((r) => asJson<RegistrationResult>(r)),
};

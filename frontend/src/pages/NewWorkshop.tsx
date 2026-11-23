import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { workshopApi } from "../api/workshop";
import { ApiError } from "../api/client";

interface ProjectItem {
  title: string;
  description: string;
  image_url: string;
  technology: string;
}

interface TimelineItem {
  step: number;
  title: string;
  description: string;
  duration: string;
}

export default function NewWorkshop() {
  const navigate = useNavigate();

  // Basic Section
  const [basic, setBasic] = useState({
    name: "",
    description: "",
    date: "",
    time: "",
    duration: "",
    venue: "",
    age_group: "",
    price: 499,
    sales_team_email: "",
    topics: "",
  });

  // Media Section
  const [media, setMedia] = useState({
    hero_image: "",
    gallery_images: [] as string[],
    instructor_image: "",
    video_url: "",
    brochure_pdf: "",
    registration_qr: "",
  });

  // Content Section
  const [learningOutcomesRaw, setLearningOutcomesRaw] = useState("");
  const [highlightsRaw, setHighlightsRaw] = useState("");
  const [projects, setProjects] = useState<ProjectItem[]>([
    { title: "", description: "", image_url: "", technology: "" },
  ]);
  const [journey, setJourney] = useState<TimelineItem[]>([
    { step: 1, title: "", description: "", duration: "" },
  ]);

  // Instructor Section
  const [instructor, setInstructor] = useState({
    name: "",
    role: "",
    bio: "",
    photo: "",
  });

  // Registration Section
  const [registration, setRegistration] = useState({
    url: "",
    button_text: "Register Now",
    seats_available: "",
    deadline: "",
    contact_email: "",
    contact_phone: "",
  });

  // UI State
  const [submitting, setSubmitting] = useState(false);
  const [uploadingField, setUploadingField] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // General Change Handlers
  const handleBasicChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;
    setBasic((prev) => ({
      ...prev,
      [name]: name === "price" ? parseFloat(value) || 0 : value,
    }));
  };

  const handleMediaChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setMedia((prev) => ({ ...prev, [name]: value }));
  };

  const handleInstructorChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;
    setInstructor((prev) => ({ ...prev, [name]: value }));
  };

  const handleRegistrationChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setRegistration((prev) => ({ ...prev, [name]: value }));
  };

  // Upload Helper
  const handleFileUpload = async (
    e: React.ChangeEvent<HTMLInputElement>,
    field: string,
    isGallery = false
  ) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setUploadingField(field);
    setError(null);

    try {
      if (isGallery) {
        const uploadedUrls: string[] = [];
        for (let i = 0; i < files.length; i++) {
          const res = await workshopApi.uploadMedia(files[i], "gallery");
          uploadedUrls.push(res.url);
        }
        setMedia((prev) => ({
          ...prev,
          gallery_images: [...prev.gallery_images, ...uploadedUrls],
        }));
      } else {
        const res = await workshopApi.uploadMedia(files[0], field);
        setMedia((prev) => ({ ...prev, [field]: res.url }));
        if (field === "instructor_image" && !instructor.photo) {
          setInstructor((prev) => ({ ...prev, photo: res.url }));
        }
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`Upload failed (${err.status}): ${err.message}`);
      } else {
        setError("Failed to upload media file. Check server connectivity.");
      }
    } finally {
      setUploadingField(null);
      e.target.value = "";
    }
  };

  // Project Handlers
  const handleProjectChange = (
    index: number,
    field: keyof ProjectItem,
    value: string
  ) => {
    setProjects((prev) => {
      const copy = [...prev];
      copy[index] = { ...copy[index], [field]: value };
      return copy;
    });
  };

  const addProject = () => {
    setProjects((prev) => [
      ...prev,
      { title: "", description: "", image_url: "", technology: "" },
    ]);
  };

  const removeProject = (index: number) => {
    setProjects((prev) => prev.filter((_, i) => i !== index));
  };

  // Timeline Handlers
  const handleTimelineChange = (
    index: number,
    field: keyof TimelineItem,
    value: string | number
  ) => {
    setJourney((prev) => {
      const copy = [...prev];
      copy[index] = { ...copy[index], [field]: value };
      return copy;
    });
  };

  const addTimelineStep = () => {
    setJourney((prev) => [
      ...prev,
      { step: prev.length + 1, title: "", description: "", duration: "" },
    ]);
  };

  const removeTimelineStep = (index: number) => {
    setJourney((prev) =>
      prev
        .filter((_, i) => i !== index)
        .map((item, i) => ({ ...item, step: i + 1 }))
    );
  };

  // Gallery Handlers
  const removeGalleryImage = (index: number) => {
    setMedia((prev) => ({
      ...prev,
      gallery_images: prev.gallery_images.filter((_, i) => i !== index),
    }));
  };

  // Submit Handler
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!basic.name.trim()) {
      setError("Workshop name is required.");
      return;
    }
    if (!basic.description.trim()) {
      setError("Workshop description is required.");
      return;
    }
    if (basic.price < 0) {
      setError("Price cannot be negative.");
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const topicList = basic.topics
        ? basic.topics
            .split(",")
            .map((t) => t.trim())
            .filter(Boolean)
        : [];
      const learningOutcomes = learningOutcomesRaw
        ? learningOutcomesRaw
            .split("\n")
            .map((l) => l.trim())
            .filter(Boolean)
        : [];
      const highlights = highlightsRaw
        ? highlightsRaw
            .split("\n")
            .map((h) => h.trim())
            .filter(Boolean)
        : [];

      const filteredProjects = projects.filter((p) => p.title.trim());
      const filteredJourney = journey.filter((j) => j.title.trim());

      const payload = {
        name: basic.name.trim(),
        description: basic.description.trim(),
        date: basic.date,
        time: basic.time,
        duration: basic.duration,
        venue: basic.venue,
        age_group: basic.age_group,
        price: basic.price,
        topics: topicList,
        poster_path: media.hero_image || undefined,
        video_url: media.video_url || undefined,
        sales_team_email: basic.sales_team_email.trim(),
        media: {
          hero_image: media.hero_image || undefined,
          gallery_images: media.gallery_images,
          instructor_image: media.instructor_image || instructor.photo || undefined,
          video_url: media.video_url || undefined,
          brochure_pdf: media.brochure_pdf || undefined,
          registration_qr: media.registration_qr || undefined,
        },
        content: {
          learning_outcomes: learningOutcomes,
          highlights: highlights,
          projects: filteredProjects,
          journey: filteredJourney,
        },
        instructor: {
          name: instructor.name || undefined,
          role: instructor.role || undefined,
          bio: instructor.bio || undefined,
          photo: instructor.photo || media.instructor_image || undefined,
        },
        registration: {
          url: registration.url || undefined,
          button_text: registration.button_text || "Register Now",
          seats_available: registration.seats_available
            ? parseInt(registration.seats_available, 10)
            : undefined,
          deadline: registration.deadline || undefined,
          contact_email: registration.contact_email || basic.sales_team_email || undefined,
          contact_phone: registration.contact_phone || undefined,
        },
      };

      const res = await workshopApi.createWorkshop(payload);
      navigate(`/workshops/${res.workshop_id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`Failed to create workshop (${err.status}): ${err.message}`);
      } else {
        setError("Network error while communicating with backend. Make sure FastAPI server is running.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AppShell title="Create New Workshop" crumbs="OPERATIONS / WORKSHOPS / NEW">
      <div style={{ padding: "24px 32px", maxWidth: 920, margin: "0 auto" }}>
        {/* Header */}
        <div style={{ marginBottom: 28 }}>
          <Link
            to="/workshops"
            style={{
              fontSize: 13,
              color: "var(--brand-primary)",
              textDecoration: "none",
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              marginBottom: 8,
            }}
          >
            ← Back to Workshops
          </Link>
          <h1 style={{ fontSize: 24, fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
            Create Complete Workshop Draft
          </h1>
          <p style={{ fontSize: 13.5, color: "var(--text-muted)", marginTop: 4, margin: 0 }}>
            Provide basic details, media, content modules, instructor profile, and registration parameters for the Workshop Agent.
          </p>
        </div>

        {/* Error Banner */}
        {error && (
          <div
            style={{
              padding: "14px 18px",
              background: "rgba(239, 68, 68, 0.1)",
              border: "1px solid rgba(239, 68, 68, 0.3)",
              borderRadius: 8,
              color: "#f87171",
              fontSize: 13.5,
              marginBottom: 24,
            }}
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 28 }}>
          {/* SECTION A — BASIC DETAILS */}
          <div className="card" style={{ padding: 28, display: "flex", flexDirection: "column", gap: 20 }}>
            <div style={{ borderBottom: "1px solid var(--border-color)", paddingBottom: 12 }}>
              <h2 style={{ fontSize: 16, fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
                1. Basic Workshop Details
              </h2>
            </div>

            <div>
              <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
                Workshop Name *
              </label>
              <input
                type="text"
                name="name"
                required
                placeholder="e.g. AI & Robotics STEM Explorer Workshop"
                value={basic.name}
                onChange={handleBasicChange}
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  borderRadius: 6,
                  border: "1px solid var(--border-color)",
                  background: "var(--bg-main)",
                  color: "var(--text-primary)",
                  fontSize: 14,
                }}
              />
            </div>

            <div>
              <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
                Description *
              </label>
              <textarea
                name="description"
                required
                rows={4}
                placeholder="Provide a comprehensive overview of what kids/students will learn..."
                value={basic.description}
                onChange={handleBasicChange}
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  borderRadius: 6,
                  border: "1px solid var(--border-color)",
                  background: "var(--bg-main)",
                  color: "var(--text-primary)",
                  fontSize: 14,
                  fontFamily: "inherit",
                }}
              />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div>
                <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
                  Date
                </label>
                <input
                  type="text"
                  name="date"
                  placeholder="e.g. 25 August 2026"
                  value={basic.date}
                  onChange={handleBasicChange}
                  style={{
                    width: "100%",
                    padding: "10px 14px",
                    borderRadius: 6,
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-main)",
                    color: "var(--text-primary)",
                    fontSize: 14,
                  }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
                  Time & Duration
                </label>
                <input
                  type="text"
                  name="time"
                  placeholder="e.g. 10:00 AM - 1:00 PM (3 Hours)"
                  value={basic.time}
                  onChange={handleBasicChange}
                  style={{
                    width: "100%",
                    padding: "10px 14px",
                    borderRadius: 6,
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-main)",
                    color: "var(--text-primary)",
                    fontSize: 14,
                  }}
                />
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div>
                <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
                  Venue / Location
                </label>
                <input
                  type="text"
                  name="venue"
                  placeholder="e.g. Jayanagar Tech Hub / Online"
                  value={basic.venue}
                  onChange={handleBasicChange}
                  style={{
                    width: "100%",
                    padding: "10px 14px",
                    borderRadius: 6,
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-main)",
                    color: "var(--text-primary)",
                    fontSize: 14,
                  }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
                  Target Age Group
                </label>
                <input
                  type="text"
                  name="age_group"
                  placeholder="e.g. Ages 8-14"
                  value={basic.age_group}
                  onChange={handleBasicChange}
                  style={{
                    width: "100%",
                    padding: "10px 14px",
                    borderRadius: 6,
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-main)",
                    color: "var(--text-primary)",
                    fontSize: 14,
                  }}
                />
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div>
                <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
                  Registration Price (₹) *
                </label>
                <input
                  type="number"
                  name="price"
                  required
                  min="0"
                  step="1"
                  value={basic.price}
                  onChange={handleBasicChange}
                  style={{
                    width: "100%",
                    padding: "10px 14px",
                    borderRadius: 6,
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-main)",
                    color: "var(--text-primary)",
                    fontSize: 14,
                  }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
                  Sales Team Contact Email
                </label>
                <input
                  type="email"
                  name="sales_team_email"
                  placeholder="e.g. sales@kiddypi.com"
                  value={basic.sales_team_email}
                  onChange={handleBasicChange}
                  style={{
                    width: "100%",
                    padding: "10px 14px",
                    borderRadius: 6,
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-main)",
                    color: "var(--text-primary)",
                    fontSize: 14,
                  }}
                />
              </div>
            </div>

            <div>
              <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
                Key Topics (Comma Separated)
              </label>
              <input
                type="text"
                name="topics"
                placeholder="e.g. Robotics, Ultrasonic Sensors, Block Coding, MicroPython"
                value={basic.topics}
                onChange={handleBasicChange}
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  borderRadius: 6,
                  border: "1px solid var(--border-color)",
                  background: "var(--bg-main)",
                  color: "var(--text-primary)",
                  fontSize: 14,
                }}
              />
            </div>
          </div>

          {/* SECTION B — WORKSHOP MEDIA */}
          <div className="card" style={{ padding: 28, display: "flex", flexDirection: "column", gap: 20 }}>
            <div style={{ borderBottom: "1px solid var(--border-color)", paddingBottom: 12 }}>
              <h2 style={{ fontSize: 16, fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
                2. Workshop Media
              </h2>
            </div>

            {/* Hero Image */}
            <div>
              <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
                Hero / Banner Image
              </label>
              <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                <input
                  type="text"
                  name="hero_image"
                  placeholder="https://... or upload image"
                  value={media.hero_image}
                  onChange={handleMediaChange}
                  style={{
                    flex: 1,
                    padding: "10px 14px",
                    borderRadius: 6,
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-main)",
                    color: "var(--text-primary)",
                    fontSize: 14,
                  }}
                />
                <label className="btn btn--secondary" style={{ cursor: "pointer", padding: "10px 16px", fontSize: 13 }}>
                  {uploadingField === "hero_image" ? "Uploading..." : "Upload File"}
                  <input
                    type="file"
                    accept="image/*"
                    onChange={(e) => handleFileUpload(e, "hero_image")}
                    style={{ display: "none" }}
                  />
                </label>
              </div>
              {media.hero_image && (
                <div style={{ marginTop: 10, display: "flex", alignItems: "center", gap: 12 }}>
                  <img
                    src={media.hero_image}
                    alt="Hero Preview"
                    style={{ width: 120, height: 70, objectFit: "cover", borderRadius: 6, border: "1px solid var(--border-color)" }}
                  />
                  <button
                    type="button"
                    onClick={() => setMedia((prev) => ({ ...prev, hero_image: "" }))}
                    style={{ background: "none", border: "none", color: "#f87171", cursor: "pointer", fontSize: 12.5 }}
                  >
                    Remove Hero Image
                  </button>
                </div>
              )}
            </div>

            {/* Gallery Images */}
            <div>
              <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
                Workshop Gallery Images
              </label>
              <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                <label className="btn btn--secondary" style={{ cursor: "pointer", padding: "10px 16px", fontSize: 13 }}>
                  {uploadingField === "gallery" ? "Uploading..." : "+ Add Gallery Photos"}
                  <input
                    type="file"
                    accept="image/*"
                    multiple
                    onChange={(e) => handleFileUpload(e, "gallery", true)}
                    style={{ display: "none" }}
                  />
                </label>
              </div>

              {media.gallery_images.length > 0 && (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginTop: 12 }}>
                  {media.gallery_images.map((imgUrl, idx) => (
                    <div key={idx} style={{ position: "relative" }}>
                      <img
                        src={imgUrl}
                        alt={`Gallery ${idx + 1}`}
                        style={{ width: 90, height: 70, objectFit: "cover", borderRadius: 6, border: "1px solid var(--border-color)" }}
                      />
                      <button
                        type="button"
                        onClick={() => removeGalleryImage(idx)}
                        style={{
                          position: "absolute",
                          top: -6,
                          right: -6,
                          background: "#ef4444",
                          color: "#fff",
                          border: "none",
                          borderRadius: "50%",
                          width: 20,
                          height: 20,
                          cursor: "pointer",
                          fontSize: 11,
                          fontWeight: 700,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                        }}
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Video Upload / URL */}
            <div>
              <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
                Workshop Video (Upload or Video URL)
              </label>
              <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                <input
                  type="text"
                  name="video_url"
                  placeholder="https://... MP4 / YouTube URL or Upload"
                  value={media.video_url}
                  onChange={handleMediaChange}
                  style={{
                    flex: 1,
                    padding: "10px 14px",
                    borderRadius: 6,
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-main)",
                    color: "var(--text-primary)",
                    fontSize: 14,
                  }}
                />
                <label className="btn btn--secondary" style={{ cursor: "pointer", padding: "10px 16px", fontSize: 13 }}>
                  {uploadingField === "video_url" ? "Uploading..." : "Upload Video"}
                  <input
                    type="file"
                    accept="video/*"
                    onChange={(e) => handleFileUpload(e, "video_url")}
                    style={{ display: "none" }}
                  />
                </label>
              </div>
            </div>

            {/* Brochure PDF */}
            <div>
              <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
                Workshop Brochure / PDF
              </label>
              <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                <input
                  type="text"
                  name="brochure_pdf"
                  placeholder="https://... PDF URL or upload brochure"
                  value={media.brochure_pdf}
                  onChange={handleMediaChange}
                  style={{
                    flex: 1,
                    padding: "10px 14px",
                    borderRadius: 6,
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-main)",
                    color: "var(--text-primary)",
                    fontSize: 14,
                  }}
                />
                <label className="btn btn--secondary" style={{ cursor: "pointer", padding: "10px 16px", fontSize: 13 }}>
                  {uploadingField === "brochure_pdf" ? "Uploading..." : "Upload PDF"}
                  <input
                    type="file"
                    accept="application/pdf"
                    onChange={(e) => handleFileUpload(e, "brochure_pdf")}
                    style={{ display: "none" }}
                  />
                </label>
              </div>
              {media.brochure_pdf && (
                <div style={{ marginTop: 8, fontSize: 12.5, color: "var(--text-muted)", display: "flex", alignItems: "center", gap: 8 }}>
                  📄 PDF Selected: {media.brochure_pdf.split("/").pop()}
                  <button
                    type="button"
                    onClick={() => setMedia((prev) => ({ ...prev, brochure_pdf: "" }))}
                    style={{ background: "none", border: "none", color: "#f87171", cursor: "pointer", fontSize: 12 }}
                  >
                    Remove
                  </button>
                </div>
              )}
            </div>

            {/* Registration QR */}
            <div>
              <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
                Registration QR Code Image
              </label>
              <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                <input
                  type="text"
                  name="registration_qr"
                  placeholder="https://... QR image URL or upload image"
                  value={media.registration_qr}
                  onChange={handleMediaChange}
                  style={{
                    flex: 1,
                    padding: "10px 14px",
                    borderRadius: 6,
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-main)",
                    color: "var(--text-primary)",
                    fontSize: 14,
                  }}
                />
                <label className="btn btn--secondary" style={{ cursor: "pointer", padding: "10px 16px", fontSize: 13 }}>
                  {uploadingField === "registration_qr" ? "Uploading..." : "Upload QR"}
                  <input
                    type="file"
                    accept="image/*"
                    onChange={(e) => handleFileUpload(e, "registration_qr")}
                    style={{ display: "none" }}
                  />
                </label>
              </div>
              {media.registration_qr && (
                <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 12 }}>
                  <img
                    src={media.registration_qr}
                    alt="QR Code"
                    style={{ width: 64, height: 64, objectFit: "contain", borderRadius: 4, border: "1px solid var(--border-color)" }}
                  />
                  <button
                    type="button"
                    onClick={() => setMedia((prev) => ({ ...prev, registration_qr: "" }))}
                    style={{ background: "none", border: "none", color: "#f87171", cursor: "pointer", fontSize: 12 }}
                  >
                    Remove QR
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* SECTION C — WORKSHOP CONTENT */}
          <div className="card" style={{ padding: 28, display: "flex", flexDirection: "column", gap: 20 }}>
            <div style={{ borderBottom: "1px solid var(--border-color)", paddingBottom: 12 }}>
              <h2 style={{ fontSize: 16, fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
                3. Workshop Content
              </h2>
            </div>

            <div>
              <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
                What Students Will Learn (One per line)
              </label>
              <textarea
                rows={3}
                placeholder="Understand ultrasonic & infrared sensors&#10;Program autonomous obstacle avoiding robots&#10;Master basic circuit building and logic blocks"
                value={learningOutcomesRaw}
                onChange={(e) => setLearningOutcomesRaw(e.target.value)}
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  borderRadius: 6,
                  border: "1px solid var(--border-color)",
                  background: "var(--bg-main)",
                  color: "var(--text-primary)",
                  fontSize: 14,
                  fontFamily: "inherit",
                }}
              />
            </div>

            <div>
              <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
                Workshop Highlights (One per line)
              </label>
              <textarea
                rows={3}
                placeholder="100% Hands-on hardware kits provided&#10;Take home completed STEM project certificate&#10;Mentorship by certified robotics engineers"
                value={highlightsRaw}
                onChange={(e) => setHighlightsRaw(e.target.value)}
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  borderRadius: 6,
                  border: "1px solid var(--border-color)",
                  background: "var(--bg-main)",
                  color: "var(--text-primary)",
                  fontSize: 14,
                  fontFamily: "inherit",
                }}
              />
            </div>

            {/* Projects / Activities */}
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                <label style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
                  Featured Projects & Activities
                </label>
                <button
                  type="button"
                  onClick={addProject}
                  style={{
                    background: "none",
                    border: "none",
                    color: "var(--brand-primary)",
                    cursor: "pointer",
                    fontSize: 12.5,
                    fontWeight: 600,
                  }}
                >
                  + Add Project
                </button>
              </div>

              {projects.map((p, idx) => (
                <div
                  key={idx}
                  style={{
                    padding: 16,
                    borderRadius: 8,
                    background: "rgba(255,255,255,0.03)",
                    border: "1px solid var(--border-color)",
                    marginBottom: 12,
                    display: "flex",
                    flexDirection: "column",
                    gap: 12,
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontSize: 12.5, fontWeight: 700, color: "var(--text-muted)" }}>
                      Project #{idx + 1}
                    </span>
                    {projects.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeProject(idx)}
                        style={{ background: "none", border: "none", color: "#f87171", cursor: "pointer", fontSize: 12 }}
                      >
                        Remove
                      </button>
                    )}
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                    <input
                      type="text"
                      placeholder="Project Title *"
                      value={p.title}
                      onChange={(e) => handleProjectChange(idx, "title", e.target.value)}
                      style={{
                        padding: "8px 12px",
                        borderRadius: 6,
                        border: "1px solid var(--border-color)",
                        background: "var(--bg-main)",
                        color: "var(--text-primary)",
                        fontSize: 13.5,
                      }}
                    />
                    <input
                      type="text"
                      placeholder="Technology / Tools (e.g. Arduino, MicroPython)"
                      value={p.technology}
                      onChange={(e) => handleProjectChange(idx, "technology", e.target.value)}
                      style={{
                        padding: "8px 12px",
                        borderRadius: 6,
                        border: "1px solid var(--border-color)",
                        background: "var(--bg-main)",
                        color: "var(--text-primary)",
                        fontSize: 13.5,
                      }}
                    />
                  </div>
                  <input
                    type="text"
                    placeholder="Short Project Description"
                    value={p.description}
                    onChange={(e) => handleProjectChange(idx, "description", e.target.value)}
                    style={{
                      padding: "8px 12px",
                      borderRadius: 6,
                      border: "1px solid var(--border-color)",
                      background: "var(--bg-main)",
                      color: "var(--text-primary)",
                      fontSize: 13.5,
                    }}
                  />
                </div>
              ))}
            </div>

            {/* Journey / Timeline */}
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                <label style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
                  Workshop Journey / Timeline
                </label>
                <button
                  type="button"
                  onClick={addTimelineStep}
                  style={{
                    background: "none",
                    border: "none",
                    color: "var(--brand-primary)",
                    cursor: "pointer",
                    fontSize: 12.5,
                    fontWeight: 600,
                  }}
                >
                  + Add Timeline Step
                </button>
              </div>

              {journey.map((step, idx) => (
                <div
                  key={idx}
                  style={{
                    padding: 16,
                    borderRadius: 8,
                    background: "rgba(255,255,255,0.03)",
                    border: "1px solid var(--border-color)",
                    marginBottom: 12,
                    display: "flex",
                    flexDirection: "column",
                    gap: 12,
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontSize: 12.5, fontWeight: 700, color: "var(--text-muted)" }}>
                      Step #{step.step}
                    </span>
                    {journey.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeTimelineStep(idx)}
                        style={{ background: "none", border: "none", color: "#f87171", cursor: "pointer", fontSize: 12 }}
                      >
                        Remove
                      </button>
                    )}
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 12 }}>
                    <input
                      type="text"
                      placeholder="Step Title *"
                      value={step.title}
                      onChange={(e) => handleTimelineChange(idx, "title", e.target.value)}
                      style={{
                        padding: "8px 12px",
                        borderRadius: 6,
                        border: "1px solid var(--border-color)",
                        background: "var(--bg-main)",
                        color: "var(--text-primary)",
                        fontSize: 13.5,
                      }}
                    />
                    <input
                      type="text"
                      placeholder="Duration (e.g. 20 mins)"
                      value={step.duration}
                      onChange={(e) => handleTimelineChange(idx, "duration", e.target.value)}
                      style={{
                        padding: "8px 12px",
                        borderRadius: 6,
                        border: "1px solid var(--border-color)",
                        background: "var(--bg-main)",
                        color: "var(--text-primary)",
                        fontSize: 13.5,
                      }}
                    />
                  </div>
                  <input
                    type="text"
                    placeholder="Step Description"
                    value={step.description}
                    onChange={(e) => handleTimelineChange(idx, "description", e.target.value)}
                    style={{
                      padding: "8px 12px",
                      borderRadius: 6,
                      border: "1px solid var(--border-color)",
                      background: "var(--bg-main)",
                      color: "var(--text-primary)",
                      fontSize: 13.5,
                    }}
                  />
                </div>
              ))}
            </div>
          </div>

          {/* SECTION D — INSTRUCTOR DETAILS */}
          <div className="card" style={{ padding: 28, display: "flex", flexDirection: "column", gap: 20 }}>
            <div style={{ borderBottom: "1px solid var(--border-color)", paddingBottom: 12 }}>
              <h2 style={{ fontSize: 16, fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
                4. Instructor Details
              </h2>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div>
                <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
                  Instructor Name
                </label>
                <input
                  type="text"
                  name="name"
                  placeholder="e.g. Dr. Rajesh Kumar"
                  value={instructor.name}
                  onChange={handleInstructorChange}
                  style={{
                    width: "100%",
                    padding: "10px 14px",
                    borderRadius: 6,
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-main)",
                    color: "var(--text-primary)",
                    fontSize: 14,
                  }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
                  Instructor Role
                </label>
                <input
                  type="text"
                  name="role"
                  placeholder="e.g. Chief STEM Mentor & Robotics Specialist"
                  value={instructor.role}
                  onChange={handleInstructorChange}
                  style={{
                    width: "100%",
                    padding: "10px 14px",
                    borderRadius: 6,
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-main)",
                    color: "var(--text-primary)",
                    fontSize: 14,
                  }}
                />
              </div>
            </div>

            <div>
              <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
                Instructor Bio
              </label>
              <textarea
                name="bio"
                rows={3}
                placeholder="Brief professional background and achievements..."
                value={instructor.bio}
                onChange={handleInstructorChange}
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  borderRadius: 6,
                  border: "1px solid var(--border-color)",
                  background: "var(--bg-main)",
                  color: "var(--text-primary)",
                  fontSize: 14,
                  fontFamily: "inherit",
                }}
              />
            </div>

            <div>
              <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
                Instructor Photo
              </label>
              <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                <input
                  type="text"
                  name="photo"
                  placeholder="https://... photo URL or upload photo"
                  value={instructor.photo}
                  onChange={handleInstructorChange}
                  style={{
                    flex: 1,
                    padding: "10px 14px",
                    borderRadius: 6,
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-main)",
                    color: "var(--text-primary)",
                    fontSize: 14,
                  }}
                />
                <label className="btn btn--secondary" style={{ cursor: "pointer", padding: "10px 16px", fontSize: 13 }}>
                  {uploadingField === "instructor_image" ? "Uploading..." : "Upload Photo"}
                  <input
                    type="file"
                    accept="image/*"
                    onChange={(e) => handleFileUpload(e, "instructor_image")}
                    style={{ display: "none" }}
                  />
                </label>
              </div>
              {instructor.photo && (
                <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 12 }}>
                  <img
                    src={instructor.photo}
                    alt="Instructor"
                    style={{ width: 50, height: 50, borderRadius: "50%", objectFit: "cover", border: "1px solid var(--border-color)" }}
                  />
                  <button
                    type="button"
                    onClick={() => setInstructor((prev) => ({ ...prev, photo: "" }))}
                    style={{ background: "none", border: "none", color: "#f87171", cursor: "pointer", fontSize: 12 }}
                  >
                    Remove Photo
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* SECTION E — REGISTRATION / CTA */}
          <div className="card" style={{ padding: 28, display: "flex", flexDirection: "column", gap: 20 }}>
            <div style={{ borderBottom: "1px solid var(--border-color)", paddingBottom: 12 }}>
              <h2 style={{ fontSize: 16, fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
                5. Registration & CTA Settings
              </h2>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div>
                <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
                  Registration URL
                </label>
                <input
                  type="text"
                  name="url"
                  placeholder="Custom URL (Optional)"
                  value={registration.url}
                  onChange={handleRegistrationChange}
                  style={{
                    width: "100%",
                    padding: "10px 14px",
                    borderRadius: 6,
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-main)",
                    color: "var(--text-primary)",
                    fontSize: 14,
                  }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
                  Button Text
                </label>
                <input
                  type="text"
                  name="button_text"
                  placeholder="Register Now"
                  value={registration.button_text}
                  onChange={handleRegistrationChange}
                  style={{
                    width: "100%",
                    padding: "10px 14px",
                    borderRadius: 6,
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-main)",
                    color: "var(--text-primary)",
                    fontSize: 14,
                  }}
                />
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div>
                <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
                  Seats Available
                </label>
                <input
                  type="number"
                  name="seats_available"
                  min="0"
                  placeholder="e.g. 25"
                  value={registration.seats_available}
                  onChange={handleRegistrationChange}
                  style={{
                    width: "100%",
                    padding: "10px 14px",
                    borderRadius: 6,
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-main)",
                    color: "var(--text-primary)",
                    fontSize: 14,
                  }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
                  Registration Deadline
                </label>
                <input
                  type="text"
                  name="deadline"
                  placeholder="e.g. 24 August 2026, 6:00 PM"
                  value={registration.deadline}
                  onChange={handleRegistrationChange}
                  style={{
                    width: "100%",
                    padding: "10px 14px",
                    borderRadius: 6,
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-main)",
                    color: "var(--text-primary)",
                    fontSize: 14,
                  }}
                />
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div>
                <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
                  Contact Email
                </label>
                <input
                  type="email"
                  name="contact_email"
                  placeholder="e.g. support@kiddypi.com"
                  value={registration.contact_email}
                  onChange={handleRegistrationChange}
                  style={{
                    width: "100%",
                    padding: "10px 14px",
                    borderRadius: 6,
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-main)",
                    color: "var(--text-primary)",
                    fontSize: 14,
                  }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
                  Contact Phone Number
                </label>
                <input
                  type="text"
                  name="contact_phone"
                  placeholder="e.g. +91 98765 43210"
                  value={registration.contact_phone}
                  onChange={handleRegistrationChange}
                  style={{
                    width: "100%",
                    padding: "10px 14px",
                    borderRadius: 6,
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-main)",
                    color: "var(--text-primary)",
                    fontSize: 14,
                  }}
                />
              </div>
            </div>
          </div>

          {/* Form Actions */}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginBottom: 40 }}>
            <Link
              to="/workshops"
              className="btn btn--secondary"
              style={{ padding: "10px 20px", textDecoration: "none", fontSize: 13.5 }}
            >
              Cancel
            </Link>
            <button
              type="submit"
              disabled={submitting || uploadingField !== null}
              className="btn btn--primary"
              style={{ padding: "10px 24px", fontSize: 13.5, fontWeight: 600 }}
            >
              {submitting ? "Creating Workshop Draft..." : "Create Workshop Draft"}
            </button>
          </div>
        </form>
      </div>
    </AppShell>
  );
}

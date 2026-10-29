import { galleryFormSchema } from "../../schemas/gallery/form";
import type { GalleryFormState, GalleryPayload } from "@/app/features/admin/types/gallery/form";

export function galleryPayload(state: GalleryFormState): GalleryPayload {
  const values = galleryFormSchema.parse(state);
  
  return {
    ...values,
    enable_sales: values.included_photo_mode === "all" ? false : values.enable_sales,
    included_photo_mode: values.included_photo_mode,
    included_photo_limit: values.included_photo_mode === "client" ? values.included_photo_limit : 0,
    default_photo_price:
      values.default_photo_price == null ? null : values.default_photo_price.toFixed(2),
    gallery_price:
      values.enable_sales && values.gallery_price !== undefined
        ? values.gallery_price.toFixed(2)
        : null,
    allow_individual_purchase:
      values.included_photo_mode !== "all" &&
      values.enable_sales &&
      (values.allow_individual_purchase || values.included_photo_mode === "client"),
    access_code: values.access_type === "private" ? values.access_code || undefined : undefined,
  };
}

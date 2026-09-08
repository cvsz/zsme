import { Suspense } from "react";

import {
  DocumentWorkbench,
  DocumentWorkbenchFallback,
} from "@/components/design-system/document-workbench";

export default function InvoicesPage() {
  return (
    <Suspense fallback={<DocumentWorkbenchFallback kind="invoice" />}>
      <DocumentWorkbench kind="invoice" />
    </Suspense>
  );
}

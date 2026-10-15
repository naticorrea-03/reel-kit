// faces <png>... -> JSON {path: [[x,y,w,h],...]} in top-left pixel coords
import Foundation
import Vision
import AppKit
var out: [String: [[Double]]] = [:]
for p in CommandLine.arguments.dropFirst() {
    guard let img = NSImage(contentsOfFile: p), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { out[p] = []; continue }
    let W = Double(cg.width), H = Double(cg.height)
    let req = VNDetectFaceRectanglesRequest()
    try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
    out[p] = (req.results ?? []).filter { $0.confidence > 0.5 }.map { f in
        let b = f.boundingBox
        return [b.minX * W, (1 - b.maxY) * H, b.width * W, b.height * H]
    }
}
let d = try! JSONSerialization.data(withJSONObject: out)
FileHandle.standardOutput.write(d)
